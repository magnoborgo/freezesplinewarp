import nuke
try:
    import bvfx_freezesplinewarp
except:
    pass

#===============================================================================
# BVFX ToolBar Menu definitions
#===============================================================================
toolbar = nuke.menu("Nodes")
bvfxt = toolbar.addMenu("BoundaryVFX Tools", "BoundaryVFX.png")
bvfxt.addCommand('Freeze Splinewarp', 'bvfx_freezesplinewarp.main()','F8')
