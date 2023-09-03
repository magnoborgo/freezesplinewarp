import nuke
import nukescripts
import nuke.rotopaint as rp
import nuke.splinewarp as sw
import _curveknob as ck
import os
import sys
import logging


log = logging.getLogger(__name__)
log.info("Loading %s " % os.path.abspath(__file__))

BVFX_DEFAULT_SHORTCUT = "F8"
BVFX_DEFAULT_MENULABEL = "Freeze Splinewarp"

__version__ = "3.0.0"
__author__ = "Magno Borgo"
__creation__ = "Mar 31 2012"
__date__ = "Set 01 2023"
__web__ = "www.boundaryvfx.com"


import os
import nuke
import logging
log = logging.getLogger(__name__)
log.info("Loading %s " % os.path.abspath(__file__))


def addTabtoNode(node,tab):
    """ Adds a custom tab to the node, skipping if a tab with the name already exists
    
    Args:
        node (Node): The node to create the tab into        
        tab (str): New tab name
    """
    knob_names = [knob.name() for knob in node.allKnobs()]

    if (tab in knob_names and node[tab].Class() != 'Tab_Knob') or (tab not in knob_names):
        new_tab = nuke.Tab_Knob(tab)
        node.addKnob(new_tab)
    else:
        log.debug("Tab already exists")
        new_tab = node[tab]
        
    return new_tab

def bvfx_signature(node,text):
    k = nuke.Text_Knob("") # divider
    k.setFlag(nuke.STARTLINE)
    node.addKnob(k)
    k = nuke.Text_Knob("")
    header = '''<span style="color:#aaa;font-family:sans-serif;font-size:8pt">'''
    extratext = '''<br>by <a href="https://github.com/magnoborgo/" style="color:#aaa">Magno Borgo</a>\nBoundary Visual Effects</span>'''

    k.setValue(header+text+extratext)
    node.addKnob(k)


def bvfx_roto_walker(rotoNode,rotoList=[]):
    """ This will traverse the rotonode hierarchy tree and generate a list with the [element, parent]
        Attention: it ignores Strokes

    Args:
        rotoNode (TYPE): a Roto or Rotopaint Node
        rotoList (list, optional): the list to return

    Returns:
        TYPE: List with [element, parent]
    """
    try:
        if rotoNode.Class() in ('Roto', 'RotoPaint'):  # its the Node
            rotoRoot = rotoNode['curves'].rootLayer
            rotoList=[] # need to restart the list otherwise it can re-use from previous runs

    except:  # its a Layer
        rotoRoot = rotoNode #usually a layer

    for _ in rotoRoot:
        if isinstance(_, nuke.rotopaint.Shape):
            rotoList.append((_, rotoRoot))
        if isinstance(_, nuke.rotopaint.Layer):
            rotoList.append((_, rotoRoot))
            bvfx_roto_walker(_, rotoList)
    return rotoList

def bvfx_TTM(point, transf, frame):
    """TTM is short for "Transform To Matrix" 
        It will apply the matrix transform on the point resulting in the new point coordinates
    
    Args:
        point (TYPE): a tuple with the original x,y coordinate
        transf (TYPE): a transform that has a matrix() method like _curvelib.AnimCTransform 
        frame (TYPE): the frame to evaluate
    
    Returns:
        TYPE: Description
    
    """
    matrix = transf.evaluate(frame).getMatrix() 
    vector = nuke.math.Vector4(point[0], point[1], 1, 1)
    x = (vector[0] * matrix[0]) + (vector[1] *
                                        matrix[1]) + matrix[2] + matrix[3]
    y = (vector[0] * matrix[4]) + (vector[1] *
                                        matrix[5]) + matrix[6] + matrix[7]
    z = (vector[0] * matrix[8]) + (vector[1] *
                                        matrix[9]) + matrix[10] + matrix[11]
    w = (vector[0] * matrix[12]) + (vector[1] *
                                         matrix[13]) + matrix[14] + matrix[15]
    vector = nuke.math.Vector4(x, y, z, w)
    vector = vector / w
    return vector


def bvfx_TL(point, Layer, frame, shapeList):
    """ Recursively apply Layers matrix/transformations on a point until reaching the roto.root
    
    Args:
        point (TYPE): a tuple with the original x,y coordinate
        Layer (TYPE): the layer to applyt the transform from
        frame (TYPE): frame to evaluate
        shapeList (TYPE): a bvfx_roto_walker() list
    
    Returns:
        TYPE: Description
    """
    newpoint = bvfx_TTM(point, Layer.getTransform(), frame)

    if not Layer == shapeList[0][1]: # its a Layer (shapeList[0][1] has always roto.root on it)
        newpoint = bvfx_TTM(point, Layer.getTransform(), frame)
        for _ in shapeList:
            if _[0] == Layer:
                newpoint = bvfx_TL(
                    newpoint, _[1], frame, shapeList)
    return newpoint





def set_inputs(node, *inputs):
    """
    Sets inputs of the passed node in the order of the passed input nodes.
    The first node will become input 0 and so on
    This code was borrowed from Julik Tarkhanov projectionist, thank you :)
    """
    for idx, one_input in enumerate(inputs):
        node.setInput(idx, one_input)


def warp_walker(nodeRoot, shapelist=[]):
    """ walks recursevely on the splinewarp tree and return a list of shapes and strokes

    Args:
        obj (TYPE): the root layer of a splinewarp
        list (TYPE): a list

    Returns:
        TYPE: Description
    """
    for i in nodeRoot:
        if isinstance(i, sw.Shape) or isinstance(i, ck.Stroke):
            shapelist.append(i)
        else:
            warp_walker(i, shapelist)
    return shapelist


def splinewarp_expressionLock(warpNode):
    """ Adds an expression on the rotoshape animation, to freeze it in place on
        the desired frame "fframe" 

        It will tag rotoshapes with the [F] in the name, so in future runs 
        it wont try to add the expression again

    Args:
        warpNode (node): splinewarp3 node
    """
    curves = warpNode['curves']
    nodeRoot = curves.rootLayer
    shapelist = warp_walker(nodeRoot, [])

    for shape in shapelist:
        shapeattr = shape.getAttributes()
        # task.setMessage('Setting expressions on' + shape.name)
        if shapeattr.getValue(0, "ab") == 1.0:
            if shape.name.count("[F]") <= 0:
                shape.name = shape.name + "_[F]"
            if isinstance(shape, ck.Stroke):
                for point in shape:
                    newcurve = point.getPositionAnimCurve(0)
                    newcurve.useExpression = True
                    newcurve.expressionString = "curve([value fframe])"
                    newcurve = point.getPositionAnimCurve(1)
                    newcurve.useExpression = True
                    newcurve.expressionString = "curve([value fframe])"
            if isinstance(shape, sw.Shape):
                for point in shape:
                    newcurve = point.center.getPositionAnimCurve(0)
                    newcurve.useExpression = True
                    newcurve.expressionString = "curve([value fframe])"
                    newcurve = point.center.getPositionAnimCurve(1)
                    newcurve.useExpression = True
                    newcurve.expressionString = "curve([value fframe])"

    curves.changed()


def splinewarp_checkAB(warpNode):
    """ Given a splinewarp node check if there are shapes on both splinewarp sides (A/B)
        If shapes are only on one side: duplicate and join shapes

    Args:
        splinewarpNode (node): Description

    """
    a = 0
    b = 0

    curves = warpNode['curves']
    nodeRoot = curves.rootLayer
    shapelist = warp_walker(nodeRoot, [])

    # checks if shapes are only in one side A or B

    for shape in shapelist:
        shapeattr = shape.getAttributes()
        abvalue = shapeattr.getValue(0, "ab")

        if abvalue == 1.0:
            a += 1
        elif abvalue == 2.0:
            b += 1
        if a > 0 and b > 0:
            break

    if not (a > 0 and b > 0):  # one side is not present
        pairs = []
        for shape in shapelist:
            new = shape.clone()
            new.name = shape.name + "_clone"
            shapeattr = new.getAttributes()
            abvalue = shapeattr.set("ab", 2.0)
            pairs.append([shape.name, new.name])

        currentnode = warpNode['curves'].toScript()
        linksplinescode = " {cp x41980000 x41980000 0 0 1 {{{{1 1}} {{1 1}}} {{{1 x40b80000}} {{1 x40b80000}}} {{{1 x41280001}} {{1 x41280001}}} {{{1 x41740001}} {{1 x41740001}}}}} {a}}"
        edges = ""
        for pair in pairs:
            edges += "{edge " + pair[0] + " " + pair[1] + linksplinescode

        newscript = currentnode[:-1]+edges+"}}"
        warpNode['curves'].fromScript(newscript)


def freezewarp(nodeList):
    """ Will take a SplineWarpNode and appply the freeze expressions on it
        Shapes should be preferably baked and without Layer transforsms

    Args:
        nodeList (list): list of nodes

    """
    for _ in nodeList:
        if _.Class() not in ('SplineWarp3'):
            raise TypeError('Unsupported node type. Node must be SplineWarp')

    # ===========================================================================
    # panel setup
    # ===========================================================================
    p = nukescripts.panels.PythonPanel("Freeze SplineWarp")
    k = nuke.Int_Knob("freezeframe", "Freezeframe")
    k.setFlag(nuke.STARTLINE)
    k.setTooltip("Set the frame to freeze the shapes positions")
    p.addKnob(k)
    k.setValue(nuke.frame())
    k = nuke.Boolean_Knob("fh", "Create FrameHold")
    k.setFlag(nuke.STARTLINE)
    k.setTooltip(
        "This will create a Framehold Node and set it to the Freezeframe value, if you use expressions mode it will be linked")
    p.addKnob(k)
    k.setValue(True)
    k = nuke.Boolean_Knob("stb", "Stabilize Setup")
    k.setFlag(nuke.STARTLINE)
    k.setTooltip("This will create a handy warp stabilization setup")
    p.addKnob(k)
    k.setValue(False)
    # ===========================================================================

    result = p.showModalDialog()

    if result == 0:  # Cancelled
        return

    freezeFrame = p.knobs()["freezeframe"].value()
    # dont put strings in there, nuke will crash
    freezeFrame = freezeFrame if isinstance(freezeFrame, int) else nuke.frame()

    fh = p.knobs()["fh"].value()
    stb = p.knobs()["stb"].value()

    # holds all nodes for selection at end of script
    nodeSelection = nodeList[:]
    # =======================================================================
    # add freeze tab / expressions to freeze
    # =======================================================================
    for warpNode in nodeList:
        splinewarp_checkAB(warpNode)
        addTabtoNode(warpNode, 'FreezeFrame')
        knob_names = [knob.name() for knob in warpNode.allKnobs()]
        if 'fframe' not in knob_names:
            ff = nuke.Int_Knob('fframe', "Freeze Frame")
            warpNode.addKnob(ff)

            pbutton = nuke.PyScript_Knob(
                'pybutton', 'This Frame', 'nuke.thisNode()["fframe"].setValue(nuke.frame())')
            warpNode.addKnob(pbutton)

            pb2code = '''origmix = nuke.thisNode()["mix"].getValue()\nnuke.thisNode()["mix"].setValue(nuke.thisNode()["root_warp"].getValue())\nnuke.thisNode()["root_warp"].setValue(origmix)
            '''
            pbutton2 = nuke.PyScript_Knob(
                'pybutton2', 'Swap mix/rootwarp', pb2code)
            warpNode.addKnob(pbutton2)

            bvfx_signature(
                warpNode, "FreezeSplinewarp v%s created %s - updated %s" % (__version__, __creation__, __date__))
            warpNode['fframe'].setValue(freezeFrame)

        splinewarp_expressionLock(warpNode)

        label = '''FreezeF: [value fframe]\n[if {[value mix]==0 && [value root_warp]==1} {return "matchmove"} {return "stabilization"}]'''
        warpNode.knob('label').setValue(label)
        warpNode.knob('filter').setValue(
            'Mitchell')  # less smoother than cubic

        # ===========================================================================
        # framehold creation
        # ===========================================================================

        if fh:
            framehold = nuke.nodes.FrameHold()

            framehold["first_frame"].setExpression(warpNode.name() + ".fframe")
            # =======================================================================
            # some layout beautyfication
            # =======================================================================
            framehold["xpos"].setValue(warpNode["xpos"].getValue() - 100)
            framehold["ypos"].setValue(warpNode["ypos"].getValue() - 80)
            dot = nuke.nodes.Dot()
            dot["xpos"].setValue(warpNode["xpos"].getValue()+34)
            dot["ypos"].setValue(framehold["ypos"].getValue()+7)
            dot2 = nuke.nodes.Dot()
            dot2["xpos"].setValue(warpNode["xpos"].getValue() - 150)
            dot2["ypos"].setValue(warpNode["ypos"].getValue()+84)
            sc = nuke.nodes.ShuffleCopy()

            sc["xpos"].setValue(warpNode["xpos"].getValue())
            sc["ypos"].setValue(warpNode["ypos"].getValue()+80)
            premult = nuke.nodes.Premult()
            premult["ypos"].setValue(sc["ypos"].getValue()+80)
            set_inputs(warpNode, dot)
            set_inputs(dot, framehold)
            set_inputs(sc, warpNode, dot2)
            set_inputs(premult, sc)

            # set_inputs(dot, framehold)
            nodeSelection += [dot, dot2, sc, framehold, premult]
            # nodeSelection.append(dot)

        # =======================================================================
        # stabilization setup
        # =======================================================================
        for _ in nuke.selectedNodes():
            _.knob('selected').setValue(False)
        warpNode.knob('selected').setValue(True)

        if stb:
            # windows copypaste bug workaround
            if sys.platform not in ('darwin') and not platform.startswith('linux'):
                tempWarpNode = nuke.createNode(warpNode.Class())
                for knobname in warpNode.knobs():
                    tempWarpNode[knobname].fromScript(
                        warpNode[knobname].toScript())
                b_input = tempWarpNode

            else:
                nukescripts.node_copypaste()
                b_input = nuke.selectedNode()

            # windows copypaste bug workaround
            if sys.platform not in ('darwin') and not platform.startswith('linux'):
                tempWarpNode = nuke.createNode(warpNode.Class())
                for knobname in warpNode.knobs():
                    tempWarpNode[knobname].fromScript(
                        warpNode[knobname].toScript())
                a_input = tempWarpNode
            else:
                nukescripts.node_copypaste()
                a_input = nuke.selectedNode()

            b_input["mix"].setValue(1)
            dot = nuke.nodes.Dot()
            set_inputs(a_input, b_input)
            set_inputs(b_input, dot)
            nukescripts.swapAB(b_input)
            dot["xpos"].setValue(warpNode["xpos"].getValue()+169)
            dot["ypos"].setValue(warpNode["ypos"].getValue()+11)
            b_input["xpos"].setValue(warpNode["xpos"].getValue()+135)
            b_input["ypos"].setValue(dot["ypos"].getValue()+80)
            a_input["xpos"].setValue(warpNode["xpos"].getValue()+135)
            a_input["ypos"].setValue(dot["ypos"].getValue()+160)            
            # =======================================================================
            # workaround.... if node is not show on properties tab the "root warp" attribute will not change!
            # =======================================================================
            b_input.knob('selected').setValue(True)
            nuke.show(nuke.selectedNode())
            nuke.selectedNode()["root_warp"].setValue(0)

            nodeSelection += [dot, b_input, a_input]

    for _ in nodeSelection:
        _.knob('selected').setValue(True)


def convert_trackernodes(trackNode, warpNode, fRange, fullbake=False):
    """ Convert Trackers into Pins (single point roto points) into a a Splinewarp node
        works with both Tracker3 or Track4 classes
    Args:
        rotoNode (TYPE): origin Tracker node
        warpNode (TYPE): destination SplineWarp node
        fRange (TYPE): framerange to convert
    """
    warpCurve = warpNode['curves']
    warpRoot = warpNode['curves'].rootLayer
    # NEED to create on a roto node, otherwise the AB attribute thing wont work
    tempRotoNode = nuke.createNode('Roto')
    rotoCurve = tempRotoNode['curves']

    if trackNode.Class() == "Tracker3":

        # ---------------------------------------------------------- #
        task = nuke.ProgressTask(
            'Converting %s to Splinewarp' % trackNode.name())
        taskcount = 1
        # ---------------------------------------------------------- #

        for _ in range(1, 5):
            if trackNode["enable"+str(_)].getValue():
                # ---------------------------------------------------------- #
                task.setMessage('Converting tracker ' + str(_))
                if task.isCancelled():
                    break
                # ---------------------------------------------------------- #

                newPointShape = rp.Shape(rotoCurve, type="bspline")
                newPoint = rp.ShapeControlPoint(0, 0)
                newPointShape.name = trackNode.name() + "_track" + str(_)
                for f in fRange:
                    newPoint.center.addPositionKey(
                        f, trackNode["track"+str(_)].getValueAt(f))

                # ===============================================================
                # cleanup repeated keyframes
                # ===============================================================
                if not fullbake:
                    for f in fRange:
                        if f not in (fRange.first(), fRange.last()):
                            lastf_point = (newPoint.center.getPositionAnimCurve(0).evaluate(
                                f-1), newPoint.center.getPositionAnimCurve(1).evaluate(f-1))
                            point = (newPoint.center.getPositionAnimCurve(0).evaluate(
                                f), newPoint.center.getPositionAnimCurve(1).evaluate(f))
                            if point == lastf_point:
                                newPoint.center.removePositionKey(f)

                shapeattr = newPointShape.getAttributes()
                shapeattr.add("ab", 1.0)
                newPointShape.append(newPoint)
                warpRoot.insert(0, newPointShape)

        del(task)

    if trackNode.Class() == "Tracker4":
        # ===============================================================
        # find the amount of trackers inside this Tracker4 mess
        numTracks = 0
        for _ in range(1, 1000):
            check = nuke.tcl(
                "value {0}.tracks.{1}.track_x".format(trackNode.name(), _))
            if check == '1':
                numTracks = _ - 1
                break
        # ===============================================================
        # ---------------------------------------------------------- #
        task = nuke.ProgressTask(
            'Converting %s to Splinewarp' % trackNode.name())
        subtask = nuke.ProgressTask('Track %s' % _)
        taskcount = 1
        # ---------------------------------------------------------- #
        for _ in range(numTracks):

            # ---------------------------------------------------------- #
            task.setMessage('Converting tracker ' + str(_))
            task.setProgress(int(float(taskcount)/numTracks*100.0))
            if task.isCancelled() or subtask.isCancelled():
                break
            # ---------------------------------------------------------- #

            newPointShape = rp.Shape(rotoCurve, type="bspline")
            newPoint = rp.ShapeControlPoint(0, 0)
            newPointShape.name = trackNode.name() + "_track" + str(_ + 1)

            # ---------------------------------------------------------- #
            subtask.setMessage('Track %s' % _)
            # ---------------------------------------------------------- #

            for f in fRange:

                # ---------------------------------------------------------- #
                tprogress = int((f - fRange.first()+1.0) /
                                (fRange.last() - fRange.first()+1.0) * 100.0)

                if tprogress % 5 == 0:   # reduce task update to every n% so its doesnt slow down calculations
                    subtask.setProgress(int(tprogress))
                if task.isCancelled() or subtask.isCancelled():
                    break
                # ---------------------------------------------------------- #
                x = trackNode['tracks'].getValueAt(f, 31 * _ + 2)
                y = trackNode['tracks'].getValueAt(f, 31 * _ + 3)
                newPoint.center.addPositionKey(f, (x, y))

            # ===============================================================
            # cleanup repeated keyframes
            # ===============================================================
            if not fullbake:
                for f in fRange:
                    if f not in (fRange.first(), fRange.last()):
                        lastf_point = (newPoint.center.getPositionAnimCurve(0).evaluate(
                            f-1), newPoint.center.getPositionAnimCurve(1).evaluate(f-1))
                        point = (newPoint.center.getPositionAnimCurve(0).evaluate(
                            f), newPoint.center.getPositionAnimCurve(1).evaluate(f))
                        if point == lastf_point:
                            newPoint.center.removePositionKey(f)

            shapeattr = newPointShape.getAttributes()
            shapeattr.add("ab", 1.0)
            newPointShape.append(newPoint)

            warpRoot.insert(0, newPointShape)
            taskcount += 1
        del(task)
        del(subtask)

    nuke.delete(tempRotoNode)


def convert_rotonodes(rotoNode, warpNode, fRange, breakintopin=False, fullbake=False):
    """Convert a Roto or Rotopaint node into a Splinewarp node
        It will: bake all the transforms on the rotoshapes
        It will: ignore feather and bezier handles

    Args:
        rotoNode (TYPE): origin Roto node
        warpNode (TYPE): destination SplineWarp node
        fRange (TYPE): framerange to convert
        breakintopin (bool, optional): Will convert the shape into individual points
    """

    rotoNode.knob("selected").setValue(True)
    # since were are manipulating shapes in place, create a node copy
    nukescripts.node_copypaste()  # this is essential to the execution

    tempRotoNode = nuke.selectedNode()
    warpRoot = warpNode['curves'].rootLayer
    rotoRoot = tempRotoNode['curves'].rootLayer
    rptsw_shapeList = bvfx_roto_walker(tempRotoNode)

    # ---------------------------------------------------------- #
    task = nuke.ProgressTask('Converting %s to Splinewarp' % rotoNode.name())
    taskcount = 0
    # ---------------------------------------------------------- #
    for shape in rptsw_shapeList:
        if task.isCancelled():
            break
        if isinstance(shape[0], nuke.rotopaint.Shape):

            task.setMessage('Converting ' + shape[0].name)
            task.setProgress(int(float(taskcount)/len(rptsw_shapeList)*100.0))

            warpCurve = warpNode['curves']
            warpRoot = warpCurve.rootLayer
            shapeattr = shape[0].getAttributes()
            shapeattr.add("ab", 1.0)
            transf = shape[0].getTransform()
            pt = 1  # counter

            # ---------------------------------------------------------- #
            subtask = nuke.ProgressTask('Converting %s' % shape[0].name)
            # ---------------------------------------------------------- #

            for points in shape[0]:
                if task.isCancelled() or subtask.isCancelled():
                    break
                newPointShape = rp.Shape(
                    tempRotoNode['curves'], type="bspline")
                newpoint = rp.ShapeControlPoint(
                    0, 0) if breakintopin else points

                # ===============================================================
                # bake all the keyframes before starting processing points
                # ===============================================================
                for f in fRange:
                    # ---------------------------------------------------------- #
                    if task.isCancelled() or subtask.isCancelled():
                        break

                    tprogress = int((f - fRange.first()+1.0) /
                                    (fRange.last() - fRange.first()+1.0) * 100.0)

                    if tprogress % 10 == 0:   # reduce task update to every n% so its doesnt slow down calculations
                        subtask.setMessage(
                            'Converting pt %s of  %s' % (pt, len(shape[0])))
                        subtask.setProgress(int(tprogress))
                    # ---------------------------------------------------------- #

                    transf.addTransformKey(f)
                    point = (points.center.getPositionAnimCurve(0).evaluate(
                        f), points.center.getPositionAnimCurve(1).evaluate(f))
                    newpoint.center.addPositionKey(f, (point[0], point[1]))
                # ===============================================================
                # end of baking process
                # ===============================================================
                lastf_point_offset = -1

                for f in fRange:
                    if task.isCancelled():
                        break

                    transf.addTransformKey(f)
                    point = (points.center.getPositionAnimCurve(0).evaluate(
                        f), points.center.getPositionAnimCurve(1).evaluate(f))
                    newpoint.center.addPositionKey(f, (point[0], point[1]))
                    transf = shape[0].getTransform()
                    center_xy = bvfx_TTM(point, transf, f)
                    center_xy = bvfx_TL(
                        center_xy, shape[1], f, rptsw_shapeList)
                    newpoint.center.addPositionKey(
                        f, (center_xy[0], center_xy[1]))

                # ===============================================================
                # cleanup repeated keyframes
                # ===============================================================
                if not fullbake:
                    for f in fRange:
                        # do not add repeated keyframes
                        if f not in (fRange.first(), fRange.last()):
                            lastf_point = (newpoint.center.getPositionAnimCurve(0).evaluate(
                                f-1), newpoint.center.getPositionAnimCurve(1).evaluate(f-1))
                            point = (newpoint.center.getPositionAnimCurve(0).evaluate(
                                f), newpoint.center.getPositionAnimCurve(1).evaluate(f))

                            if point == lastf_point:
                                newpoint.center.removePositionKey(f)

                # ===============================================================
                # cleanup keyframes outside range
                # ===============================================================
                for f in newpoint.center.getControlPointKeyTimes():
                    if not fRange.isInRange(int(f)):
                        newpoint.center.removePositionKey(f)

                if breakintopin:
                    newPointShape.name = "%s_PIN[%s]" % (
                        shape[0].name, str(pt))
                    newPointShape.append(newpoint)
                    shapeattr = newPointShape.getAttributes()
                    shapeattr.add("ab", 1.0)
                    warpRoot.insert(0, newPointShape)

                pt += 1

            if not breakintopin:
                transf = shape[0].getTransform()
                for f in fRange:
                    transf.removeTransformKey(f)
                transf.reset()
                # ===========================================================================
                # fix the curve Extramatrix for the range of the conversion
                # ===========================================================================
                identmatrix = [(0, 0, 1), (0, 1, 0), (0, 2, 0), (0, 3, 0), (1, 0, 0), (1, 1, 1), (1, 2, 0), (
                    1, 3, 0), (2, 0, 0), (2, 1, 0), (2, 2, 1), (2, 3, 0), (3, 0, 0), (3, 1, 0), (3, 2, 0), (3, 3, 1)]
                extramatrix = transf.evaluate(fRange.first()).getMatrix()
                for m in identmatrix:
                    curve = transf.getExtraMatrixAnimCurve(m[0], m[1])
                    curve.removeAllKeys()
                    curve.addKey(fRange.first(), m[2])
                    curve.removeAllKeys()
                # ===========================================================================
                # move shapes to new home
                # ===========================================================================
                warpRoot.insert(0, shape[0])

        taskcount += 1

    rotoNode.knob("selected").setValue(False)
    nuke.delete(tempRotoNode)
    del(rptsw_shapeList)
    del(task)  # always delete task
    del(subtask)


def convert_into_splinewarp(nodeList):
    # ===========================================================================
    # panel setup
    # ===========================================================================
    p = nukescripts.panels.PythonPanel("Convert to Splinewarp")
    k = nuke.String_Knob("framerange", "FrameRange")
    k.setFlag(nuke.STARTLINE)
    k.setTooltip(
        "Set the framerange to convert, by default its the project start-end. Example: 10-20")
    p.addKnob(k)
    k.setValue("%s-%s" % (nuke.root().firstFrame(), nuke.root().lastFrame()))
    k = nuke.Boolean_Knob("pin", "Break into Pin Points")
    k.setFlag(nuke.STARTLINE)
    k.setTooltip("This will break all the shapes into single points")
    p.addKnob(k)
    k = nuke.Boolean_Knob("fullbake", "Full bake")
    k.setFlag(nuke.STARTLINE)
    k.setTooltip("Adds keyframes on all frames inside the range")
    p.addKnob(k)
    result = p.showModalDialog()
    # ===========================================================================

    if result == 0:
        return  # Canceled
    try:
        fRange = nuke.FrameRange(p.knobs()["framerange"].getText())
    except:
        raise ValueError(
            'Framerange format is not correct, use startframe-endframe i.e.: 0-200')

    breakintopin = p.knobs()["pin"].value()
    fullbake = p.knobs()["fullbake"].value()

    # main warpnode creation
    warpNode = nuke.createNode('SplineWarp3')
    warpNode.knob("selected").setValue(False)
    for _ in nodeList:
        if _.Class() in ('Roto', 'RotoPaint'):
            convert_rotonodes(_, warpNode, fRange, breakintopin, fullbake)

        if _.Class() in ('Tracker3', 'Tracker4'):
            convert_trackernodes(_, warpNode, fRange, fullbake)

    ####
    # TODO keyframe cleanup ? way too many repeated baked keyframes
    ####

    ####
    # TODO ckeck for keyframes on shapes outside the frange?
    ####

    ####
    # TODO task message
    ####

    warpNode['curves'].changed()
    warpNode.knob('toolbar_output_ab').setValue(1)
    warpNode.knob('boundary_bbox').setValue(0)

    # =======================================================================
    # theres a bug on Nuke 8 where the splinewarpnode UI do not update correctly with python created curves
    # this is a workaround
    # =======================================================================
    warpNode.knob("selected").setValue(True)
    nukescripts.node_copypaste()
    nuke.show(nuke.selectedNode())
    # nuke.selectedNode().knob('selected').setValue(False)
    # =======================================================================
    # end of workaround -
    # =======================================================================
    # rptsw_shapeList = []
    # nuke.delete(rotoNode)
    nuke.delete(warpNode)

    if nuke.selectedNode().Class() == "SplineWarp3":
        return nuke.selectedNode()  # the resulting splinewarpnode


def main():
    """ This script has 2 main purposes:

        01. Convert selected roto and trackers nodes (baking all transforms) into Splinewarps
        02. Apply the Freeze Splinewarp (via nuke expressions) on a splinewarp node.

        This is an overhaul of the original scripts from
        https://github.com/magnoborgo/RotoPaintToSplineWarp2
        https://github.com/magnoborgo/FreezeSplineWarp2

    """
    the_nodes = nuke.selectedNodes()
    trackerNodes = []
    rotoNodes = []
    splinewarpNodes = []

    if nuke.NUKE_VERSION_MAJOR < 7:
        raise TypeError("This script needs Nuke v7 or later")

    for _ in the_nodes:
        if _.Class() in ('Roto', 'RotoPaint'):
            rotoNodes.append(_)
        elif _.Class() in ('Tracker3', 'Tracker4'):
            trackerNodes.append(_)
        elif _.Class() == 'SplineWarp3':
            splinewarpNodes.append(_)

        # deselect these nodes for future operations
        _.knob("selected").setValue(False)

    if len(rotoNodes) == 0 and len(trackerNodes) == 0 and len(splinewarpNodes) == 0:
        raise TypeError("No Roto or Tracker or Splinewarp node selected")

    if (len(rotoNodes) > 0 or len(trackerNodes) > 0) and len(splinewarpNodes) > 0:
        raise TypeError(
            "Either select Roto/Trackers nodes OR Splinewarp nodes")

    nuke.Undo.name("Freeze Splinewarp")
    nuke.Undo.new()

    if len(rotoNodes) > 0 or len(trackerNodes) > 0:
        splinewarpNodes.append(convert_into_splinewarp(rotoNodes+trackerNodes))

    if len(splinewarpNodes) > 0:
        freezewarp(splinewarpNodes)

    nuke.Undo.end()


if __name__ == '__main__':
    main()
