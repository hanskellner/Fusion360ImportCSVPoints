#Author-Hans Kellner
#Description-Import X,Y,Z values from a CSV file to create points, or lines, or splines within a sketch.

import adsk.core, adsk.fusion, traceback, math, random

from . import patterns
from . import pipe
from enum import Enum

# CONSTANTS

class Sketch_Style(Enum):
    SKETCH_POINTS = 0
    SKETCH_LINES = 1
    SKETCH_FITTED_SPLINES = 2
    SKETCH_SOLID_BODY = 3
    LAST_STYLE = 3

UNIT_STRINGS = {
    'mm': 'Millimeter',
    'cm': 'Centimeter',
    'meter': 'Meter',
    'in': 'Inch',
    'ft': 'Foot'
}

_IMPORT_CSV_POINTS_CMD_ID = 'hanskellner_insert_csv_points_id'

_INSERT_PANEL_ID = 'InsertPanel'

_DROPDOWN_INPUT_ID_UNIT = 'unitDropDownInputId'
_DROPDOWN_INPUT_ID_STYLE = 'styleDropDownInputId'
_SELECTION_INPUT_ID_SOLID_BODY = 'solidBodySelectionInputId'
_SELECTION_INPUT_ID_SKETCH = 'sketchSelectionInputId'
_DROPDOWN_INPUT_ID_CONSTRUCTION_PLANE = 'constructionPlaneDropDownInputId'


_CONSTRUCTION_PLANE_XY = "XY Plane"
_CONSTRUCTION_PLANE_XZ = "XZ Plane"
_CONSTRUCTION_PLANE_YZ = "YZ Plane"

# GLOBALS

# event handlers to keep them referenced for the duration of the command
_app = adsk.core.Application.cast(None)
_ui = adsk.core.UserInterface.cast(None)

# Global set of event handlers to keep them referenced for the duration of the command
_handlers = []

# Units to use for imported points
_unit = 'cm'

# File to load
_csvFilename = ''

# Style of sketch entities to create
_style = Sketch_Style.SKETCH_LINES

# Which solid body selected
_solidBodyToClone = None

# If a sketch is selected, this is the name
_selectedSketchName = ''

# Which construction plane to place sketch when a sketch isn't specified
_constructionPlane = _CONSTRUCTION_PLANE_XY

# Command Inputs
_unitDropDownInput = adsk.core.DropDownCommandInput.cast(None)
_styleDropDownInput = adsk.core.DropDownCommandInput.cast(None)
_sketchSelectionInput = adsk.core.SelectionCommandInput.cast(None)
_constructionPlaneDropDownInput = adsk.core.DropDownCommandInput.cast(None)
_solidBodySelectionInput = adsk.core.DropDownCommandInput.cast(None)


# Get the selected sketch name; otherwise an empty string
def getSelectedSketchName():
    if _sketchSelectionInput.selectionCount == 1:
        theSelection = _sketchSelectionInput.selection(0)

        if theSelection.entity.objectType == adsk.fusion.Sketch.classType():
            return theSelection.entity.name
            
    # Nothing selected so no sketch name
    return ''

# Get the selected entity (body or component)
def getSelectedEntity():
    if _solidBodySelectionInput.selectionCount == 1:
        return _solidBodySelectionInput.selection(0).entity
    else:
        return None

# Get the selected entity style to create
def getSelectedStyle():
    return _styleDropDownInput.selectedItem.index


# Converts a value from the user selected unit to 'cm'
# Returns a pair (bool: True on success; otherwise false, Value)
def convertValue(value):
    global _app, _ui

    design = _app.activeProduct
    newVal = design.unitsManager.convert(value, _unit, 'cm')

    # unitsManager.convert() returns -1 AND GetLastError() returns ExpressionError in the event of an error.
    if newVal == -1:
        (errReturnValue, errDescription) = _app.getLastError()
        if errReturnValue == adsk.fusion.ExpressionError:
            return (False, 0)

    return (True, newVal)

# Returns total count of points in all lines
def totalPointsInLines(lines):
    count = 0
    if lines != None:
        for pts in lines:
            count += len(pts)
    return count

# Event handler for the execute event.
class MyCommandExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        eventArgs = adsk.core.CommandEventArgs.cast(args)

        global _app, _ui, _selectedSketchName, _constructionPlane, _solidBodyToClone, _csvFilename

        design = _app.activeProduct
        rootComp = design.rootComponent

        try:

            # Create file dialog to prompt for CSV file
            fileDialog = _ui.createFileDialog()
            fileDialog.isMultiSelectEnabled = False
            fileDialog.title = "Select Points CSV File"
            fileDialog.filter = 'CSV files (*.csv);;All files (*.*)'
            fileDialog.filterIndex = 0
            dialogResult = fileDialog.showOpen()
            if dialogResult != adsk.core.DialogResults.DialogOK:
                _csvFilename = ''
                return

            # This is our filename
            _csvFilename = fileDialog.filename
           
            # Set styles of progress dialog.
            progressDialog = _ui.createProgressDialog()
            progressDialog.cancelButtonText = 'Cancel'
            progressDialog.isBackgroundTranslucent = False
            progressDialog.isCancelButtonShown = True
            
            # Show progress dialog
            progressDialog.show('Importing CSV', 'Loading... %v', 0, 1000, 1)

            lineCount = 0
            skippingBlanks = False # True when skipping a set of blank lines
            
            lines = []      # list of point lists
            points3D = []   # Current Point3D list

            cmdCreatePipes = False
            argCreatePipesOuterRadius = 1
            argCreatePipesInnerRadius = 0.5     # > 0 means hollow 
            
            # Read the csv file line by line.
            file = open(_csvFilename)
            for line in file:
                
                line = line.strip()
                
                # Is this line empty?  Note, also check for the case where the line contains the separators but no values.
                # This can occur when some apps, such as Excel, exports empty rows.
                if line == '' or line == ',,' or line == ',':
                    skippingBlanks = True

                    # A blank line indicates a break in the point sequence and to start
                    # a new set of points.  For example, for creating multiple lines.
                    if len(points3D) > 0:
                        lines.append(points3D)
                        points3D = []

                elif line[0] == '#':
                    pass # Skip comment lines
                
                else:
                    skippingBlanks = False
                
                    # Get the values from the csv file.
                    pieces = line.split(',')

                    if len(pieces) == 0:
                        progressDialog.hide()
                        _ui.messageBox("Invalid line: {}".format(lineCount) + "\nCSV file: {}".format(_csvFilename))
                        return

                    # check for a specific command in first piece
                    if pieces[0] == 'spiral':

                        # Need to end previous set?
                        if len(points3D) > 0:
                            lines.append(points3D)
                            points3D = []

                        # spiral needs 5 arguments: numArms, numPointsPerArm, armsOffset, rateExpansion, zStep
                        if len(pieces) != 6:
                            progressDialog.hide()
                            _ui.messageBox("Invalid 'spiral' at line: {}".format(lineCount) + "\nCSV file: {}".format(_csvFilename))
                            return
                        
                        linesSpiral = patterns.generateSpiral(int(pieces[1]), int(pieces[2]), float(pieces[3]), float(pieces[3]), float(pieces[3]))
                        if linesSpiral == None:
                            progressDialog.hide()
                            _ui.messageBox("Invalid parameters for 'spiral' at line: {}".format(lineCount) + "\nCSV file: {}".format(_csvFilename))
                            return
                        
                        lines.extend( linesSpiral )

                    elif pieces[0] == 'spiralcube':

                        # Need to end previous set?
                        if len(points3D) > 0:
                            lines.append(points3D)
                            points3D = []

                        # spiral cube needs 3 arguments: pointCount, rotationInRadians, lengthGrow
                        if len(pieces) != 4:
                            progressDialog.hide()
                            _ui.messageBox("Invalid 'spiralcube' line: {}".format(lineCount) + "\nCSV file: {}".format(_csvFilename))
                            return
                        
                        linesSpiralCube = patterns.generateSpiralCube(int(pieces[1]), float(pieces[2]), float(pieces[3]))
                        if linesSpiralCube == None:
                            progressDialog.hide()
                            _ui.messageBox("Invalid parameters for 'spiralcube' at line: {}".format(lineCount) + "\nCSV file: {}".format(_csvFilename))
                            return
                        
                        lines.extend( linesSpiralCube )

                    # Command to create pipes for all of the lines/splines read
                    # REVIEW: HACK: This is a hack to allow creating pipes.
                    elif pieces[0] == 'pipes':

                        # Need to end previous set?
                        if len(points3D) > 0:
                            lines.append(points3D)
                            points3D = []

                        # pipe needs 1 or 2 arguments: outer radius, [inner radius]
                        if (len(pieces) < 2 or len(pieces) > 3):
                            progressDialog.hide()
                            _ui.messageBox("Invalid 'pipes' line: {}".format(lineCount) + "\nCSV file: {}".format(_csvFilename))
                            return

                        cmdCreatePipes = True
                        (outerValid, argCreatePipesOuterRadius) = convertValue(float(pieces[1]))

                        if (len(pieces) == 3):
                            (innerValid, argCreatePipesInnerRadius) = convertValue(float(pieces[2]))
                        else:
                            (innerValid, argCreatePipesInnerRadius) = (True, 0)
                        
                        if not outerValid or not innerValid:
                            progressDialog.hide()
                            _ui.messageBox("Invalid pipes radius value at line: {}".format(lineCount) + "\nCSV file: {}".format(_csvFilename))
                            return

                    else:
                    
                        if (len(pieces) < 2 or len(pieces) > 3):
                            progressDialog.hide()
                            _ui.messageBox("No 2d or 3d point at line: {}".format(lineCount) + "\nCSV file: {}".format(_csvFilename))
                            return

                        (xValid, x) = convertValue(float(pieces[0]))
                        (yValid, y) = convertValue(float(pieces[1]))

                        if (len(pieces) == 3):
                            (zValid, z) = convertValue(float(pieces[2]))
                        else:
                            (zValid, z) = (True, 0)

                        if not xValid or not yValid or not zValid:
                            progressDialog.hide()
                            _ui.messageBox("Invalid number at line: {}".format(lineCount) + "\nCSV file: {}".format(_csvFilename))
                            return
                        
                        # Save this point
                        points3D.append(adsk.core.Point3D.create(x,y,z))
                    
                lineCount = lineCount + 1

                # If progress dialog is cancelled, stop drawing.
                if progressDialog.wasCancelled:
                    break

                # Update progress value of progress dialog
                progressDialog.progressValue = lineCount % 100

            # end line loop.  Check if a set if points waiting to be added.
            if len(points3D) > 0:
                lines.append(points3D)
            
            # Hide the progress dialog at the end.
            progressDialog.hide()

            # Empty file then just exit
            if len(lines) == 0:
                _ui.messageBox("No points found in CSV file: {}".format(_csvFilename))
                return

            # Creating solid bodies?
            isSolidBodyStyle = (Sketch_Style(_style) == Sketch_Style.SKETCH_SOLID_BODY)
            if isSolidBodyStyle:

                totalPonts = totalPointsInLines(lines)

                # Show progress dialog
                progressDialog.show('Generating Bodies', 'Creating %v of %m (%p)', 0, totalPonts, 1)

                bodyToClone = adsk.fusion.BRepBody.cast(_solidBodyToClone)

                bodyToClonePos = None

                newComp = rootComp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
                newComp.component.name = 'Import CSV Points'

                # Check to see if the body is in the root component or another one.
                #target = None
                if bodyToClone.assemblyContext:
                    # It's in another component.
                    target = bodyToClone.assemblyContext    # Occurrence

                    # Where is the body located?
                    bodyToClonePos = target.transform.translation
                else:
                    # It's in the root component.
                    target = rootComp                       # Component

                for iLine in range(len(lines)):

                    if (lines[iLine] == None or len(lines[iLine]) == 0):
                        continue

                    # For each point, create a copy of the prototype body
                    linePoints = lines[iLine]
                    for iPt in range(len(linePoints)):

                        pt = linePoints[iPt]

                        # If point is not at 0 then copy body and move to location
                        # Otherwise, keep the existing object so we don't
                        if (pt.x != 0 or pt.y != 0 or pt.z != 0):

                            # Create the copy.
                            newBody = bodyToClone.copyToComponent(newComp) #target)

                            # Move the mew body (note, relative move)
                            tx = adsk.core.Matrix3D.create()
                            tx.translation = adsk.core.Vector3D.create(pt.x, pt.y, pt.z)
                            bodyColl = adsk.core.ObjectCollection.create()
                            bodyColl.add(newBody)
                            moveInput = rootComp.features.moveFeatures.createInput(bodyColl, tx)
                            moveFeat = rootComp.features.moveFeatures.add(moveInput)

                        # If progress dialog is cancelled, stop drawing.
                        if progressDialog.wasCancelled:
                            break

                        # Update progress value of progress dialog
                        progressDialog.progressValue = iLine

                    if progressDialog.wasCancelled:
                        break

            else:   # Sketch based

                # Show progress dialog
                progressDialog.show('Generating Entities', 'Creating %v of %m (%p)', 0, len(lines), 1)

                theSketch = None

                if _selectedSketchName != '':
                    theSketch = rootComp.sketches.itemByName(_selectedSketchName)
                
                if theSketch == None:
                    # Which plane if no sketch?
                    # xYConstructionPlane, xZConstructionPlane, yZConstructionPlane
                    plane = rootComp.xYConstructionPlane
                    if _constructionPlane == _CONSTRUCTION_PLANE_XZ:
                        plane = rootComp.xZConstructionPlane
                    elif _constructionPlane == _CONSTRUCTION_PLANE_YZ:
                        plane = rootComp.yZConstructionPlane

                    theSketch = rootComp.sketches.add(plane)
                    theSketch.name = "CSV Points - " + theSketch.name

                theSketch.isComputeDeferred = True  # Help to speed up import
                theSketch.areProfilesShown = False # TESTING

                new_sketch_lines = []

                # Add sketch entities
                if Sketch_Style(_style) == Sketch_Style.SKETCH_FITTED_SPLINES:

                    for iLine in range(len(lines)):

                        if (lines[iLine] == None or len(lines[iLine]) == 0):
                            continue

                        # Create an object collection for the line points.
                        linePoints = adsk.core.ObjectCollection.create()

                        # Add the points the spline will fit through.
                        for pt in lines[iLine]:
                            linePoints.add(pt)

                        # Create the spline.
                        theSketchLine = theSketch.sketchCurves.sketchFittedSplines.add(linePoints)
                        new_sketch_lines.append(theSketchLine)

                        # If progress dialog is cancelled, stop drawing.
                        if progressDialog.wasCancelled:
                            break

                        # Update progress value of progress dialog
                        progressDialog.progressValue = iLine

                else:
                    sketch_points = theSketch.sketchPoints
                    sketch_lines = theSketch.sketchCurves.sketchLines

                    for iLine in range(len(lines)):

                        if (lines[iLine] == None or len(lines[iLine]) == 0):
                            continue

                        theFirstSketchLine = None

                        linePoints = lines[iLine]
                        linePointsCount = len(linePoints)
                        for iPt in range(linePointsCount):

                            if Sketch_Style(_style) == Sketch_Style.SKETCH_POINTS:
                                sketch_points.add(linePoints[iPt])
                            
                            elif Sketch_Style(_style) == Sketch_Style.SKETCH_LINES:
                                if iPt == 1:
                                    theSketchLine = sketch_lines.addByTwoPoints(linePoints[iPt-1], linePoints[iPt])
                                    new_sketch_lines.append(theSketchLine)
                                    theFirstSketchLine = theSketchLine
                                if iPt > 1:
                                    # Use previous sketch line's end point to start next line.  Otherwise they won't
                                    # be connected lines.  We also need to check if this is the last line and if it
                                    # has the same endpoint location as the first line's start point.  If so then we
                                    # need to use the starting lines point as the endpoint of this line.
                                    lineEndPoint = None
                                    if linePoints[iPt].x == linePoints[0].x and linePoints[iPt].y == linePoints[0].y and linePoints[iPt].z == linePoints[0].z:
                                        lineEndPoint = theFirstSketchLine.startSketchPoint
                                    else:
                                        lineEndPoint = linePoints[iPt]

                                    theSketchLine = sketch_lines.addByTwoPoints(theSketchLine.endSketchPoint, lineEndPoint)
                                    # REVIEW: Only pass first line and then use "isChain" when creating feature.path
                                    #new_sketch_lines.append(theSketchLine)

                        # If progress dialog is cancelled, stop drawing.
                        if progressDialog.wasCancelled:
                            break

                        # Update progress value of progress dialog
                        progressDialog.progressValue = iLine

                # Done creating sketch entities
                theSketch.isComputeDeferred = False
 
                # Request to create pipes and were any skecth lines added?
                if cmdCreatePipes and len(new_sketch_lines) > 0:
                    pipe.createPipesOnLines(_app, _ui, new_sketch_lines, argCreatePipesOuterRadius, argCreatePipesInnerRadius)

            # Hide the progress dialog at the end.
            progressDialog.hide()

        except:
            _ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


# Event handler that reacts to any changes the user makes to any of the command inputs.
class MyCommandInputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            global _app, _ui, _unit, _style, _constructionPlane, _selectedSketchName, _solidBodyToClone
            global _constructionPlaneDropDownInput, _unitDropDownInput, _styleDropDownInput

            des = adsk.fusion.Design.cast(_app.activeProduct)

            eventArgs = adsk.core.InputChangedEventArgs.cast(args)
            inputs = eventArgs.inputs
            changedInput = eventArgs.input

            # Need to know these anytime something changes
            _style = getSelectedStyle()
            isSolidBodyStyle = (Sketch_Style(_style) == Sketch_Style.SKETCH_SOLID_BODY)

            _solidBodyToClone = getSelectedEntity()
            isSolidBodySelected = isSolidBodyStyle and (_solidBodyToClone != None)

            if changedInput.id == _SELECTION_INPUT_ID_SOLID_BODY:
                pass

            if changedInput.id == _SELECTION_INPUT_ID_SKETCH:
                _selectedSketchName = getSelectedSketchName()

            elif changedInput.id == _DROPDOWN_INPUT_ID_CONSTRUCTION_PLANE:
                _constructionPlane = _constructionPlaneDropDownInput.selectedItem.name
            
            elif changedInput.id == _DROPDOWN_INPUT_ID_UNIT:
                unitName = _unitDropDownInput.selectedItem.name
                for keyUnit, valUnit in UNIT_STRINGS.items():
                    if valUnit == unitName:
                        _unit = keyUnit
                        break
            
            elif changedInput.id == _DROPDOWN_INPUT_ID_STYLE:
                pass

            # Update visiblity/enabled

            _solidBodySelectionInput.isVisible = isSolidBodyStyle
            if isSolidBodyStyle:
                _solidBodySelectionInput.setSelectionLimits(1, 1)
            else:
                _solidBodySelectionInput.setSelectionLimits(0)

            _sketchSelectionInput.isVisible = not isSolidBodyStyle

            _constructionPlaneDropDownInput.isVisible = not isSolidBodyStyle
            _constructionPlaneDropDownInput.isEnabled = (_selectedSketchName == '')

        except:
            _ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


# Event handler that reacts to when the command is destroyed. This terminates the script.            
class MyCommandDestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            # When the command is done, terminate the script
            # This will release all globals which will remove all event handlers
            #adsk.terminate()
            pass
        except:
            _ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


# Event handler that reacts when the command definitio is executed which
# results in the command being created and this event being fired.
class MyCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            global _app, _ui, _handlers, _unit, _csvFilename
            global _unitDropDownInput, _styleDropDownInput, _sketchSelectionInput, _constructionPlaneDropDownInput, _solidBodySelectionInput

            design = _app.activeProduct
            if not design:
                _ui.messageBox('No active Fusion design', 'No Design')
                return

            # Get the command that was created.
            cmd = adsk.core.Command.cast(args.command)

            # Connect to the command destroyed event.
            onDestroy = MyCommandDestroyHandler()
            cmd.destroy.add(onDestroy)
            _handlers.append(onDestroy)

            # Connect to the input changed event.           
            onInputChanged = MyCommandInputChangedHandler()
            cmd.inputChanged.add(onInputChanged)
            _handlers.append(onInputChanged)    

            # Get the user's current units
            _unit = design.unitsManager.defaultLengthUnits

            # Get the CommandInputs collection associated with the command.
            inputs = cmd.commandInputs

            # Create image input.
            #inputs.addImageCommandInput('image', 'Image', "resources/help.png")
            
            # Dropdown for unit used in CSV file
            _unitDropDownInput = inputs.addDropDownCommandInput(_DROPDOWN_INPUT_ID_UNIT, 'Units', adsk.core.DropDownStyles.TextListDropDownStyle)
            for keyUnit, valUnit in UNIT_STRINGS.items():
                _unitDropDownInput.listItems.add(valUnit, (_unit == keyUnit))

            isSolidBodyStyle = (Sketch_Style(_style) == Sketch_Style.SKETCH_SOLID_BODY)

            # Dropdown for the type of sketch entity to create
            _styleDropDownInput = inputs.addDropDownCommandInput(_DROPDOWN_INPUT_ID_STYLE, 'Style', adsk.core.DropDownStyles.TextListDropDownStyle)
            styleInputListItems = _styleDropDownInput.listItems
            styleInputListItems.add('Points', (Sketch_Style(_style) == Sketch_Style.SKETCH_POINTS))
            styleInputListItems.add('Lines', (Sketch_Style(_style) == Sketch_Style.SKETCH_LINES))
            styleInputListItems.add('Fitted Splines', (Sketch_Style(_style) == Sketch_Style.SKETCH_FITTED_SPLINES))
            styleInputListItems.add('Solid Body', isSolidBodyStyle)

            # Selection of body to clone for each point
            _solidBodySelectionInput = inputs.addSelectionInput(_SELECTION_INPUT_ID_SOLID_BODY, 'Body to Clone', 'Select a body to clone for each point')
            _solidBodySelectionInput.addSelectionFilter('Bodies')
            _solidBodySelectionInput.setSelectionLimits(1 if isSolidBodyStyle else 0, 1)    # HACK: OK btn still checks hidden control state
            _solidBodySelectionInput.isVisible = isSolidBodyStyle

            # Optional: Selection of sketch to add entities
            _sketchSelectionInput = inputs.addSelectionInput(_SELECTION_INPUT_ID_SKETCH, 'Sketch', 'Select a sketch or none to create a new one')
            _sketchSelectionInput.addSelectionFilter('Sketches')
            _sketchSelectionInput.setSelectionLimits(0, 1)
            _sketchSelectionInput.isVisible = not isSolidBodyStyle

            _constructionPlaneDropDownInput = inputs.addDropDownCommandInput(_DROPDOWN_INPUT_ID_CONSTRUCTION_PLANE, 'Construction Plane', adsk.core.DropDownStyles.TextListDropDownStyle)
            _constructionPlaneDropDownInput.listItems.add(_CONSTRUCTION_PLANE_XY, (_constructionPlane == _CONSTRUCTION_PLANE_XY))
            _constructionPlaneDropDownInput.listItems.add(_CONSTRUCTION_PLANE_XZ, (_constructionPlane == _CONSTRUCTION_PLANE_XZ))
            _constructionPlaneDropDownInput.listItems.add(_CONSTRUCTION_PLANE_YZ, (_constructionPlane == _CONSTRUCTION_PLANE_YZ))
            _constructionPlaneDropDownInput.isVisible = not isSolidBodyStyle

            # Setup event handlers
            onExecute = MyCommandExecuteHandler()
            cmd.execute.add(onExecute)
            _handlers.append(onExecute)

        except:
            _ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


def run(context):
    try:
        global _app, _ui, _handlers
        _app = adsk.core.Application.get()
        _ui = _app.userInterface

        # Get the existing command definition or create it if it doesn't already exist.
        cmdDef = _ui.commandDefinitions.itemById(_IMPORT_CSV_POINTS_CMD_ID)
        if not cmdDef:
            cmdDef = _ui.commandDefinitions.addButtonDefinition(_IMPORT_CSV_POINTS_CMD_ID, 'Import CSV Points', 'Imports point values from a CSV file.', './resources')
            cmdDef.toolClipFilename = './resources/tooltip.png'

        # Connect to the command events.
        onCommandCreated = MyCommandCreatedHandler()
        cmdDef.commandCreated.add(onCommandCreated)
        _handlers.append(onCommandCreated)

        # Get the INSERT panel in the MODEL workspace. 
        insertPanel = _ui.allToolbarPanels.itemById(_INSERT_PANEL_ID)

        # Add button to the panel
        btnControl = insertPanel.controls.itemById(_IMPORT_CSV_POINTS_CMD_ID)
        if not btnControl:
            btnControl = insertPanel.controls.addCommand(cmdDef)

            # Make the button available in the panel.
            btnControl.isPromotedByDefault = False
            btnControl.isPromoted = False
        
        if context['IsApplicationStartup'] is False:
            _ui.messageBox('The "Insert CSV Points" command has been\nadded to the INSERT panel dropdown.')
    except:
        if _ui:
            _ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


def stop(context):
    try:
        # Delete controls and associated command definitions created by this add-ins
        insertPanel = _ui.allToolbarPanels.itemById(_INSERT_PANEL_ID)
        
        btnControl = insertPanel.controls.itemById(_IMPORT_CSV_POINTS_CMD_ID)
        if btnControl:
            btnControl.deleteMe()
        
        cmdDef = _ui.commandDefinitions.itemById(_IMPORT_CSV_POINTS_CMD_ID)
        if cmdDef:
            cmdDef.deleteMe() 
    except:
        if _ui:
            _ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))