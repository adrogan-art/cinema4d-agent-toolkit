"""Neutral trusted driver template for cinema4d-gui-testing."""

import c4d
from c4d import documents, gui


class ProbeDialog(gui.GeDialog):
    def CreateLayout(self):
        self.SetTitle("GUI event-loop probe")
        self.AddStaticText(1000, c4d.BFH_LEFT, name="Isolated GUI test")
        return True


def run(context):
    context.check("cinema_main_thread", c4d.threading.GeIsMainThread())

    document = documents.BaseDocument()
    document.SetDocumentName("Disposable GUI Test.c4d")
    documents.InsertBaseDocument(document)
    documents.SetActiveDocument(document)
    context.add_cleanup(lambda: documents.KillDocument(document))

    probe = c4d.BaseObject(c4d.Onull)
    probe.SetName("Disposable Probe")
    document.InsertObject(probe)
    c4d.EventAdd()
    context.check("temporary_document_active", documents.GetActiveDocument() == document)
    context.check("temporary_object_inserted", document.SearchObject("Disposable Probe") == probe)

    dialog = ProbeDialog()
    context.add_cleanup(dialog.Close)
    opened = dialog.Open(dlgtype=c4d.DLG_TYPE_ASYNC, pluginid=0, defaultw=260, defaulth=90)
    context.check("async_dialog_opened", opened)
    context.artifact(
        "neutral-driver-summary.json",
        {"document": document.GetDocumentName(), "object": probe.GetName(), "dialog_opened": bool(opened)},
    )
    return {"checks": 4, "fixture": "temporary document and asynchronous GeDialog"}
