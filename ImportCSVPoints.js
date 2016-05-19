//Author-Hans Kellner
//Description-Import a set of points from a CSV file and create points/lines/splines in a sketch

/*!
Copyright (C) 2016 Hans Kellner: https://github.com/hanskellner/Fusion360ImportCSVPoints
MIT License: See https://github.com/hanskellner/Fusion360ImportCSVPoints/LICENSE.md
*/

/*
This is a script for Autodesk Fusion 360 that imports a set of points from a CSV file
and create points/lines/splines in a sketch.

Installation:

Copy this scripts folder into your Fusion 360 "My Scripts" folder. You may find this folder using the following steps:

1) Start Fusion 360 and then select the File -> Scripts... menu item
2) The Scripts Manager dialog will appear and display the "My Scripts" folder and "Sample Scripts" folders
3) Select one of the "My Scripts" files and then click on the "+" Details icon near the bottom of the dialog.
  a) If there are no files in the "My Scripts" folder then create a default one.
  b) Click the Create button, select JavaScript, and then OK.
5) With the user script selected, click the Full Path "..." button to display a file explorer window that will display the "My Scripts" folder
6) Copy the files into the folder

For example, on a Mac the folder is located in:
/Users/USERNAME/Library/Application Support/Autodesk/Autodesk Fusion 360/API/Scripts

*/

/*globals adsk*/
function run(context) {

    "use strict";

    if (adsk.debug === true) {
        /*jslint debug: true*/
        debugger;
        /*jslint debug: false*/
    }

    var SKETCH_STYLE = {
        SKETCH_POINTS: 0,
        SKETCH_LINES: 1,
        SKETCH_FITTED_SPLINES: 2,
        LAST_STYLE: 2
    };

    var SKETCH_UNITS = {
        SKETCH_UNIT_MM: 0,
        SKETCH_UNIT_CM: 1,
        SKETCH_UNIT_METER: 2,
        SKETCH_UNIT_INCH: 3,
        SKETCH_UNIT_FOOT: 4,
        LAST_UNIT: 4
    };

	var appTitle = 'Import CSV Points';

	var app = adsk.core.Application.get(), ui;
    if (app) {
        ui = app.userInterface;
        if (!ui) {
            adsk.terminate();
    		return;
        }
    }

	var design = adsk.fusion.Design(app.activeProduct);
	if (!design) {
		ui.messageBox('No active design', appTitle);
		adsk.terminate();
		return;
	}

    // Array that will contain arrays of points.
    var lines3d = [];

    // Create the command definition.
    var createCommandDefinition = function() {
        var commandDefinitions = ui.commandDefinitions;

        // Be fault tolerant in case the command is already added...
        var cmDef = commandDefinitions.itemById('ImportCSVPoints');
        if (!cmDef) {
            cmDef = commandDefinitions.addButtonDefinition('ImportCSVPoints',
                    'Import CSV Points',
                    'Import a set of points from a CSV file and create points/lines/splines in a sketch.',
                    './resources'); // relative resource file path is specified
        }
        return cmDef;
    };

    // CommandCreated event handler.
    var onCommandCreated = function(args) {
        try {
            // Connect to the CommandExecuted event.
            var command = args.command;
            command.execute.add(onCommandExecuted);

            // Terminate the script when the command is destroyed
            command.destroy.add(function () { adsk.terminate(); });

            // Define the inputs.
            var inputs = command.commandInputs;

            var unitInput = inputs.addDropDownCommandInput('unitType', 'Unit Type', adsk.core.DropDownStyles.TextListDropDownStyle );
            unitInput.listItems.add('Millimeter',false);
            unitInput.listItems.add('Centimeter',false);
            unitInput.listItems.add('Meter',true);
            unitInput.listItems.add('Inch',false);
            unitInput.listItems.add('Foot',false);

            var styleInput = inputs.addDropDownCommandInput('style', 'Style', adsk.core.DropDownStyles.TextListDropDownStyle );
            styleInput.listItems.add('Points',false);
            styleInput.listItems.add('Lines',true);
            styleInput.listItems.add('Fitted Splines',false);

            var sketchSelInput = inputs.addSelectionInput('sketchSelection', 'Sketch', 'Select a sketch or none to create a new one');
            sketchSelInput.addSelectionFilter('Sketches');
            sketchSelInput.setSelectionLimits(0, 1);
        }
        catch (e) {
            ui.messageBox('Failed to create command : ' + (e.description ? e.description : e));
        }
    };

    // CommandExecuted event handler.
    var onCommandExecuted = function(args) {
        try {

            // Extract input values
            //var unitsMgr = app.activeProduct.unitsManager;
            var command = adsk.core.Command(args.firingEvent.sender);
            var inputs = command.commandInputs;

            var styleInput, sketchSelInput, unitInput;

            // REVIEW: Problem with a problem - the inputs are empty at this point. We
            // need access to the inputs within a command during the execute.
            for (var n = 0; n < inputs.count; n++) {
                var input = inputs.item(n);
                if (input.id === 'style') {
                    styleInput = adsk.core.DropDownCommandInput(input);
                }
                else if (input.id === 'unitType') {
                    unitInput = adsk.core.DropDownCommandInput(input);
                }
                else if (input.id === 'sketchSelection') {
                    sketchSelInput = adsk.core.SelectionCommandInput(input);
                }
            }

            if (!styleInput || !sketchSelInput || !unitInput) {
                ui.messageBox("One of the inputs does not exist.");
                return;
            }

            var csvUnit = unitInput.selectedItem.index;
            if (csvUnit < 0 || csvUnit > SKETCH_UNITS.LAST_UNIT) {
                ui.messageBox("Invalid style: must be 0 to "+SKETCH_UNITS.LAST_UNIT);
                return;
            }

            // Point unit determines scale factor.  Need to convert to CMs
            var unitScale = 1;

            switch (csvUnit) {
                case SKETCH_UNITS.SKETCH_UNIT_MM:
                    unitScale = 0.1; break;
                case SKETCH_UNITS.SKETCH_UNIT_METER:
                    unitScale = 100; break;
                case SKETCH_UNITS.SKETCH_UNIT_INCH:
                    unitScale = 2.54; break;
                case SKETCH_UNITS.SKETCH_UNIT_FOOT:
                    unitScale = 25.4; break;
            }

            // Convert points if not in centimeters, the default unit of model
            if (1 !== unitScale) {
                for (var iLine = 0; iLine < lines3d.length; ++iLine) {
                    var points3d = lines3d[iLine];
                    for (var iPt = 0; iPt < points3d.length; ++iPt) {
                        var pt = points3d[iPt];
                        pt.set(pt.x * unitScale, pt.y * unitScale, pt.z * unitScale);
                    }
                }
            }

            var sketchStyle = styleInput.selectedItem.index;
            if (sketchStyle < 0 || sketchStyle > SKETCH_STYLE.LAST_STYLE) {
                ui.messageBox("Invalid style: must be 0 to "+SKETCH_STYLE.LAST_STYLE);
                return;
            }

            var rootComp = design.rootComponent;
            var sketches = rootComp.sketches;

            var sketch = null;
            // Should be 0 or 1
            if (sketchSelInput.selectionCount == 1) {
                // Get the selected sketch
                sketch = sketchSelInput.selection(0).entity;
            }
            else {
                // Create a new sketch
                var xyPlane = rootComp.xYConstructionPlane;
                sketch = sketches.add(xyPlane);
                sketch.name = "ImportCSVPoints - " + sketch.name;
            }

            // DO IT!

            sketch.isComputeDeferred = true;    // defer while modifying to speed up

            if (sketchStyle === SKETCH_STYLE.SKETCH_FITTED_SPLINES) {

                for (var iLine = 0; iLine < lines3d.length; ++iLine) {

                    if (lines3d[iLine] == null || lines3d[iLine].length == 0) {
                        continue;
                    }

                    // Create an object collection for the points.
                    var points = adsk.core.ObjectCollection.create();

                    var points3d = lines3d[iLine];
                    for (var iPt = 0; iPt < points3d.length; ++iPt) {
                        // Define the points the spline with fit through.
                        points.add(points3d[iPt]);
                    }

                    // Create the spline.
                    sketch.sketchCurves.sketchFittedSplines.add(points);
                }
            }
            else {
                var sketch_points = sketch.sketchPoints;
                var sketch_lines = sketch.sketchCurves.sketchLines;

                for (var iLine = 0; iLine < lines3d.length; ++iLine) {

                    if (lines3d[iLine] == null || lines3d[iLine].length == 0) {
                        continue;
                    }

                    var points3d = lines3d[iLine];
                    for (var iPt = 0; iPt < points3d.length; ++iPt) {

                        if (sketchStyle === SKETCH_STYLE.SKETCH_POINTS) {
                            // Add a sketch point
                            sketch_points.add(points3d[iPt]);
                        }
                        else if (sketchStyle === SKETCH_STYLE.SKETCH_LINES) {
                            // Add a sketch line
                            if (iPt > 0) {
                                sketch_lines.addByTwoPoints(points3d[iPt-1], points3d[iPt]);
                            }
                        }
                    }
                }
            }

            sketch.isComputeDeferred = false;
        }
        catch (e) {
            ui.messageBox('Failed to execute command : ' + (e.description ? e.description : e));
        }
    };

    // TODO: This can't handle large buffers
    var uintToString = function(uintArray) {
        var encodedString = String.fromCharCode.apply(null, uintArray),
            decodedString = decodeURIComponent(encodeURIComponent (encodedString));
        return decodedString;
    };

    var arrayBufferToBase64 = function( buffer ) {
        var binary = '';
        var bytes = new Uint8Array( buffer );
        var len = bytes.byteLength;
        for (var i = 0; i < len; i++) {
            binary += String.fromCharCode( bytes[ i ] );
        }
        return window.btoa( binary );
    }

    //var Uint8ToBase64 = function(u8Arr) {
    var Uint8ToString = function(u8Arr) {
        var CHUNK_SIZE = 0x8000; //arbitrary number
        var index = 0;
        var length = u8Arr.length;
        var result = '';
        var slice;
        while (index < length) {
            slice = u8Arr.subarray(index, Math.min(index + CHUNK_SIZE, length));
            result += String.fromCharCode.apply(null, slice);
            index += CHUNK_SIZE;
        }
        return result; //btoa(result);
    }

	try {

        // First prompt for the image filename
        var dlg = ui.createFileDialog();
        dlg.title = 'Select Points CSV File';
        dlg.filter = 'CSV Files (*.csv);;All Files (*.*)';
        if (dlg.showOpen() == adsk.core.DialogResults.DialogOK) {

            var csvFilename = dlg.filename;

            var lines3dindex = 0;   // Which line array we are populating

            // Read the csv file.
            var cnt = 0;
            var arrayBuffer = adsk.readFile(csvFilename);
            //var allLines = uintToString(new Uint8Array(arrayBuffer));
            //var allLines = String.fromCharCode.apply(null, new Uint8Array(arrayBuffer));
            //var allLines = arrayBufferToBase64(arrayBuffer);
            //var encodedString = String.fromCharCode.apply(null, new Uint8Array(arrayBuffer));
            //var allLines = decodeURIComponent(encodeURIComponent (encodedString));
            var allLines = Uint8ToString(new Uint8Array(arrayBuffer));

            var linesCSV = allLines.split(/\r?\n/);

            var linesCSVCount = linesCSV.length;
            for (var i = 0; i < linesCSVCount; ++i) {

                var line = linesCSV[i].trim();

                // Is this line empty?
                if (line === "") {
                    // A blank line indicates a break in the point sequence and to start
                    // a new set of points.  For example, for creating multiple lines.
                    // If we have any lines then bump index to start a new line.
                    if (lines3d.length > 0) {
                        lines3dindex = lines3dindex + 1;    // Next line
                    }

                    // Skip over multiple blank lines (treat as one)
                    for (++i ; line === "" && i < linesCSVCount; ++i) {
                        line = linesCSV[i].trim();
                    }

                    if (i == linesCSVCount) {
                        break;  // No more lines
                    }
                }

                // Get the values from the csv file.
                var pieces = line.split(',');

                if ( pieces.length < 2 || pieces.length > 3 ) {
                    ui.messageBox("No 2d or 3d point at line: " + cnt + " - CSV file: " + csvFilename);
                    adsk.terminate();
                }

                if (isNaN(pieces[0]) || isNaN(pieces[1]) || (pieces.length == 3 && isNaN(pieces[2]))) {
                    ui.messageBox("Invalid number at line: " + cnt + " - CSV file: " + csvFilename);
                    adsk.terminate();
                }

                var x = Number(pieces[0]);
                var y = Number(pieces[1]);
                var z = (pieces.length === 3) ? Number(pieces[2]) : 0;

                // Get the point array for the current line
                // but first check if we need to add a new array
                if (lines3d.length === lines3dindex) {
                    lines3d.push(new Array());
                }

                var points3d = lines3d[lines3dindex];

                // Save this point
                points3d.push( adsk.core.Point3D.create(x,y,z) );

                cnt += 1;
            }

            // Create and run command
            var command = createCommandDefinition();
            var commandCreatedEvent = command.commandCreated;
            commandCreatedEvent.add(onCommandCreated);

            command.execute();
        }
        else {
            adsk.terminate();
        }
    }
    catch (e) {
        if (ui) {
            ui.messageBox('ImportCSVPoints Script Failed : ' + (e.description ? e.description : e));
            adsk.terminate();
        }
    }
}
