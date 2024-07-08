import lspcpp
from os import path
DEFAULT_ROOT = "/home/z/dev/lsp/pylspclient/tests/test-workspace"
def test_client_init():
    lspcppserver = lspcpp.lspcppserver()
    cfg = lspcpp.project_config()
    cfg.DEFAULT_ROOT=DEFAULT_ROOT
    client = lspcppserver.newclient(cfg)
    assert(client !=None)