"""Module for pre/post-processing."""

import logging

import slicer 

from ..processing import register_processing

@register_processing("output", "render_3d", ["segmentation"], {
    None: {
        "smoothing": {
            "name": "Surface Smoothing Factor",
            "type": "float",
            "min": 0,
            "max": 1,
            "default": 0.5,
        }
    }
})
def render_3d(op, op_config, node, *args, **kwargs):
    name = slicer.vtkBinaryLabelmapToClosedSurfaceConversionRule.GetSmoothingFactorParameterName()
    node.GetSegmentation().SetConversionParameter(name, str(op_config["params"]["smoothing"]))
    node.CreateClosedSurfaceRepresentation()

@register_processing(None, "seged", ["segmentation"], None)
def seged(op, op_config, node, node_config, model, model_config):
    """Segment editor processing."""
    sew = slicer.qMRMLSegmentEditorWidget()
    sew.setMRMLScene(slicer.mrmlScene)
    sen = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
    sew.setMRMLSegmentEditorNode(sen)
    segmentation = node.GetSegmentation()
    sew.setSegmentationNode(node)
    sew.setActiveEffectByName(op["action"])

    if not op["targets"]:
        op["targets"] = range(segmentation.GetNumberOfSegments())
    
    if "master" in node_config:
        mv = model_config["inputs"][node_config["master"]]["value"]
    else:
        mv = None
    sew.setMasterVolumeNode(mv)

    for n in op["targets"]:
        logging.info("- Applying to segment %d" % n)

        sew.setCurrentSegmentID(segmentation.GetNthSegmentID(n))
        effect = sew.activeEffect()
        if effect is None:
           raise Exception("Unknown seged action: %s" % op["action"])

        for p, v in op_config["params"].items():
            effect.setParameter(p, str(v))
        
        effect.self().onApply()
    
    sew.setActiveEffectByName(None)
    slicer.mrmlScene.RemoveNode(sen)
