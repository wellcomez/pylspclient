from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import files
from typing import Optional
from textual.message import Message
from textual.validation import Failure
from textual.widgets import Label, ListItem, ListView, Tree

from lspcpp import CallNode, task_call_in


class uicallback:

    def on_vi_command(self, value: str):
        pass

    def on_command_input(self, value):
        pass

    def on_select_list(self, list: ListView):
        pass


class MyListView(ListView):
    mainui: uicallback

    def setlist(self, data: list[str]):
        self.clear()
        self.extend(list(map(lambda x: ListItem(Label(x)), data)))

    def _on_list_item__child_clicked(self,
                                     event: ListItem._ChildClicked) -> None:
        ListView._on_list_item__child_clicked(self, event)
        self.mainui.on_select_list(self)

    def action_select_cursor(self):
        self.mainui.on_select_list(self)


class callinopen(Message):

    def __init__(self, node: object) -> None:
        super().__init__()
        self.node = node


class CallTreeNode:
    callnode: Optional[CallNode | task_call_in]
    treenode_id: Optional[str] = None
    job_id: int
    nodecount: int = 0

    def __init__(self, callnode: Optional[CallNode | task_call_in],
                 jobid: int) -> None:
        self.callnode = callnode
        self.focused = False
        self.job_id = jobid
        pass


class _calltree(Tree, uicallback):
    BINDINGS = [
        ("r", "refer", "resolve"),
        ("a", "resolve_all", "resolve_all"),
    ]

    def action_resolve_all(self) -> None:
        try:
            for child in self.root.children:
                if child != self.cursor_node:
                    continue
                if child.data is None:
                    continue
                parent: CallTreeNode = child.data
                if parent is None or isinstance(parent.callnode,
                                                task_call_in) == False:
                    continue
                task: task_call_in = parent.callnode  # type: ignore
                ThreadPoolExecutor(1).submit(task.deep_resolve)
                return
        except:
            pass
        pass

    def action_refer(self) -> None:
        try:
            for child in self.root.children:
                if child.data is None:
                    continue
                parent: CallTreeNode = child.data
                if parent is None or isinstance(parent.callnode,
                                                task_call_in) == False:
                    continue
                task: task_call_in = parent.callnode  # type: ignore
                index = child.children.index(self.cursor_node)  # type: ignore
                if index >= 0:
                    aa = child.children[index]
                    if aa.data != None:

                        def fn(task, index):
                            task.deep_resolve_at(index)

                        ThreadPoolExecutor(1).submit(fn, task, index)
                    break

        except:
            pass
        pass

    def __init__(self):
        Tree.__init__(self, "call heritage")

    def action_toggle_node(self):
        pass

    def action_enter(self):
        pass

    def action_select_cursor(self):
        try:
            self.__action_select_cursor()
        except:
            pass

    def __action_select_cursor(self):
        if self.cursor_node != None and self.cursor_node.data != None:
            n: CallTreeNode = self.cursor_node.data
            if n != None:
                open = n.focused == False
                if n.focused:
                    n.focused = False
                else:
                    n.focused = True
                if open:
                    self.app.post_message(callinopen(n.callnode))
                else:
                    if self.cursor_node.is_expanded:
                        cur = self.cursor_node
                        child = cur.children[0] if len(cur.children) else None
                        while child != None:
                            call = child.data
                            if call != None:
                                call.focused = False
                            child = child.children[0] if len(
                                child.children) else None

                    self.cursor_node.toggle_all()


class callinview:
    job: task_call_in
    status: str = ""
    findresult = []
    index = 0
    tree_node_list: list[CallTreeNode] = []

    def __init__(self) -> None:
        self.tree = _calltree()

    def goto_next(self):
        if len(self.findresult):
            self.index += 1
            self.index = self.index % len(self.findresult)
            self.tree.select_node(self.findresult[self.index])  # type: ignore

    def find_text(self, text):
        self.index = 0

        def find_node(node, key) -> list:
            if node is None:
                return []
            ret = []
            if str(node.label).lower().find(key) > -1:
                ret.append(node)
            if node.is_expanded:
                for c in node.children:
                    ret.extend(find_node(c, key))
            return ret

        self.findresult = find_node(self.tree.root, text)
        if len(self.findresult):
            self.tree.select_node(self.findresult[self.index])  # type: ignore

    def update_exists_node(self, job: task_call_in):
        for a in job.resolve_task_list:
            for stacknode in a.node.callstack():
                try:
                    def cmp(node: CallTreeNode):
                        if job.id != node.job_id:
                            return False
                        return stacknode == node.callnode

                    ret = list(filter(cmp, self.tree_node_list))
                    if len(ret) == 1:
                        treenode = self.tree.get_node_by_id(
                            int(ret[0].treenode_id))  # type: ignore
                        if treenode is None:
                            return False
                        treenode.label = stacknode.displayname()
                    else:
                        return False
                except Exception as e:
                    return False
        return True

    # mainui:uicallback
    def update_job(self, job: task_call_in):
        self.job = job
        jobid = job.id
        for child in self.tree.root.children:
            if child.data is None:
                continue
            c: CallTreeNode = child.data
            if isinstance(c.callnode, task_call_in):
                task: task_call_in = c.callnode
                if task.id == job.id:
                    if c.nodecount == job.all_stacknode_cout() and self.update_exists_node(job):
                        return
                    child.remove()
                    break
        data = CallTreeNode(job, jobid=jobid)
        data.nodecount = job.all_stacknode_cout()
        root = self.tree.root.add(job.method.name, expand=True, data=data)
        data.treenode_id = str(root.id)
        self.tree_node_list.append(data)
        for a in job.callin_all:
            level = 1
            subroot = node = root.add(a.displayname(),
                                      data=CallTreeNode(a, jobid=jobid),
                                      expand=False)
            a = a.callee
            while a != None:
                level += 1
                data = CallTreeNode(a, jobid=jobid)
                if a.callee is None:
                    node = node.add_leaf(a.displayname(), data=data)
                    break
                else:
                    node = node.add(a.displayname(), data=data)
                data.treenode_id = str(node.id)
                self.tree_node_list.append(data)
                a = a.callee
            ss = subroot.label
            subroot.label = "%d %s" % (level, ss)
