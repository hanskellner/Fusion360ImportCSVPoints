#Author-Hans Kellner
#Description-Function for generating pipes along sketch lines.

import adsk.core, adsk.fusion, traceback, math, random

# Generate pipes that follow each specified sketch line
# @arg rootComp
# @arg sketchLines
# @arg outerRadius
# @arg innerRadius

def createPipesOnLines(app, ui, sketchLines, outerDiam, innerDiam):

        design = app.activeProduct
        rootComp = design.rootComponent
        sketches = rootComp.sketches
        feats = rootComp.features

        for line in sketchLines:

            try:

                if False:

                    # Command implementation
                    # NOTE: This crashes Fusion.  Possiby because the commands are executed within addin command?
                    sels :adsk.core.Selections = ui.activeSelections
                    sels.clear()
                    sels.add(line) #path)

                    txtCmds = [
                        u'Commands.Start PrimitivePipe', # show dialog
                        u'Commands.SetDouble SWEEP_POP_ALONG 1.0', # input distance
                        u'Commands.SetDouble SectionRadius 0.5', # input radius
                        u'NuCommands.CommitCmd' # execute command
                    ]
                
                    for cmd in txtCmds:
                        app.executeTextCommand(cmd)

                    sels.clear()

                else:

                    # create path
                    path = feats.createPath(line, True)

                    # create profile
                    planes = rootComp.constructionPlanes
                    planeInput = planes.createInput()
                    planeInput.setByDistanceOnPath(path, adsk.core.ValueInput.createByReal(0))
                    plane = planes.add(planeInput)

                    sketch = sketches.add(plane)

                    center = sketch.modelToSketchSpace(plane.geometry.origin)

                    circleOuter = sketch.sketchCurves.sketchCircles.addByCenterRadius(center, outerDiam)
                    circleInner = None
                    if innerDiam > 0:
                        circleInner = sketch.sketchCurves.sketchCircles.addByCenterRadius(center, innerDiam)

                    profileOuter = sketch.profiles[0]

                    # create sweep for outer
                    sweepFeats = feats.sweepFeatures
                    sweepInputOuter = sweepFeats.createInput(profileOuter, path, adsk.fusion.FeatureOperations.JoinFeatureOperation)
                    sweepInputOuter.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
                    sweepFeat = sweepFeats.add(sweepInputOuter)

            except:
                print("Unexpected error")
