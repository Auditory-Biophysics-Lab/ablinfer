"""Module for integrating ABLInfer into Slicer."""

import logging

import os
import slicer

from .. import DispatchBase
from ..docker import DispatchDocker
from ..remote import DispatchRemote

from .processing import __name__ as _

class SlicerDispatchMixin(DispatchBase):
    """Mixin for dispatching from Slicer.

    A ``tmp_path`` key is added to ``config``, which must contain the location to store temporary
    files for dispatching.

    This class does not implement any actual dispatching; this must be combined with the 
    appropriate dispatcher to function properly, e.g.::

        class SlicerDispatchActual(SlicerDispatchMixin, DispatchActual):
            pass
    """
    def __init__(self, config):
        self.tmp_path = None
        self._input_nodes = {}

        super().__init__(config)

    def _validate_config(self):
        super()._validate_config()

        self.tmp_path = self.config["tmp_path"]
        if not os.path.isdir(self.tmp_path):
            os.makedirs(self.tmp_path)

    @staticmethod
    def _clone(a, b=None):
        """Try to clone a node.

        This is copied from qSlicerSubjectHierarchyModuleLogic.cxx, I can't figure out how to call 
        that directly and it doesn't support cloning into another node anyways.

        @param a the original node 
        @param b the node to clone into; if None, creates one
        @returns the created node
        """
        ## TODO: Move this in to an external library?
        if b is None:
            b = slicer.mrmlScene.AddNewNodeByClass(a.GetClassName())
            name = a.GetName()
        else:
            name = b.GetName()

        ## Clone the display node
        a_dn = a.GetDisplayNode()
        if b.GetDisplayNode():
            b_dn = b.GetDisplayNode()
        else:
            b_dn = slicer.mrmlScene.AddNewNodeByClass(a_dn.GetClassName())
            b_dn.Copy(a_dn)
            b_dn.SetName(name + "_Display")
            b.SetAndObserveDisplayNodeID(b_dn.GetID())

        ## Clone storage node
        a_sn = a.GetStorageNode()
        if a_sn:
            if b.GetStorageNode():
                b_sn = b.GetStorageNode()
            else:
                b_sn = slicer.mrmlScene.AddNewNodeByClass(a_sn.GetClassName())
                b_sn.Copy(a_sn)
                if a_sn.GetFileName():
                    b_sn.SetFileName(a_sn.GetFileName())
                b.SetAndObserveStorageNodeID(b_sn.GetID())

        ## Finally, do the copy
        b.Copy(a)
        b.SetName(name)

        b.SetAndObserveDisplayNodeID(b_dn)
        b.SetAndObserveStorageNodeID(b_sn)

        ## Trigger update
        b_ptn = b.GetParentTransformNode()
        if b_ptn:
            b_ptn.Modified()

        return b

    def _save_input(self, fmap):
        self._input_nodes = {}

        for k, v in self.model["inputs"].items():
            ## Don't use os.path.join here: the Docker container might not have the same OS as the 
            ## host machine, which is where we are now. Forward slashes should work on any system,
            ## so just use them here; we already removed any trailing slash from actual_path
            lpath = os.path.join(self.tmp_path, k+v["extension"])
            ## Write it to the path on the local machine
            if k in self._pre_nodes:
                actual_node = self._pre_nodes[k]
            else:
                actual_node = self.model_config["inputs"][k]["value"]
            ret = slicer.util.saveNode(actual_node, lpath)
            self._created_files.append(lpath)

            self._input_nodes[k] = self.model_config["inputs"][k]["value"]
            self.model_config["inputs"][k]["value"] = lpath

            if not ret:
                raise Exception("Unable to save input \"%s\" to file. THIS SHOULD NOT HAPPEN" % v["name"])

        ## Now let the actual dispatcher put the files into the container
        super()._save_input(fmap)

    def _load_output(self, fmap):
        output_nodes = {}
        ## Point the dispatcher to the local files
        for k, v in self.model_config["outputs"].items():
            output_nodes[k] = v.copy()
            v["value"] = os.path.join(self.tmp_path, k+self.model["outputs"][k]["extension"])

        ## Load them to the local disk
        super()._load_output(fmap=fmap)

        ## Restore the input nodes
        for k, v in self._input_nodes.items():
            self.model_config["inputs"][k]["value"] = v

        ## Now load them into Slicer
        for k, member in self.model["outputs"].items():
            logging.info("Loading \"%s\"..." % member["name"])
            of = self.model_config["outputs"][k]["value"]
            if member["type"] == "segmentation":
                if member["labelmap"]:
                    logging.info("- Loading as LabelVolume")
                    _, lvnode = slicer.util.loadLabelVolume(of, returnNode=True)
                    if lvnode is None:
                        raise Exception("Missing output %s! Please report this." % member["name"])
                    node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
                    logging.info("- Converting to segmentation")
                    slicer.vtkSlicerSegmentationsModuleLogic.ImportLabelmapToSegmentationNode(lvnode, node, "")
                    slicer.mrmlScene.RemoveNode(lvnode)
                else:
                    _, node = slicer.util.loadSegmentation(of, returnNode=True)

                ## Fill in the colours and names

                ## First, map the label values to the actual segment objects
                segmap = {}
                segmentation = node.GetSegmentation()
                display_node = node.GetDisplayNode()
                if display_node is None:
                    logging.warning("Can't find display node for segmentation, opacity will be skipped")
                for i in range(segmentation.GetNumberOfSegments()):
                    thisseg = segmentation.GetNthSegment(i), segmentation.GetNthSegmentID(i)
                    segmap[thisseg.GetLabelValue()] = thisseg

                ## Now set the names and colours
                for label in set(member["colours"]).union(member["names"]):
                    try:
                        ilabel = int(label)
                    except ValueError:
                        logging.warning("Invalid label %s, ignoring" % (repr(label)))
                        continue
                    if ilabel not in segmap:
                        logging.warning("Couldn't find segment matching label %d, ignoring" % label)
                        continue
                    theseg, theid = segmap[ilabel]
                    if label in member["colours"]:
                        thecolour = member["colours"][label]
                        theseg.SetColor(tuple(thecolour[:3]))
                        if len(thecolour) == 4: ## Opacity
                            dn.SetSegmentOpacity4D(theid, thecolour[3])
                    if label in member["names"]:
                        theseg.SetName(member["names"][label])

            elif member["type"] == "volume":
                if member["labelmap"]:
                    _, node = slicer.util.loadLabelVolume(of, returnNode=True)
                else:
                    _, node = slicer.util.loadVolume(of, returnNode=True)
            else:
                raise Exception("Unknown output type %s" % repr(member["type"]))

            ## Make sure the output is where it should be
            if output_nodes[k]["value"] is not None:
                ## Clone it
                self.clone(node, output_nodes[k]["value"])
                slicer.mrmlScene.RemoveNode(node)
                node = output_nodes[k]["value"]

            self.model_config["outputs"][k]["value"] = node

    def _cleanup(self, error=None):
        ## Get rid of output too
        self._created_files.extend(self._output_files)
        super()._cleanup(error=error)
        
        ## Remove the pre-processing clones
        for v in self._pre_nodes.values():
            slicer.mrmlScene.RemoveNode(v)
        self._pre_nodes = {}
        self._input_nodes = {}

class SlicerDispatchDocker(SlicerDispatchMixin, DispatchDocker):
    """Convenience class for dispatching to Docker from Slicer."""
    pass

class SlicerDispatchRemote(SlicerDispatchMixin, DispatchRemote):
    """Convenience class for dispatching to an ABLInfer server from Slicer."""
    pass
