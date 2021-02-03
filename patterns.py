#Author-Hans Kellner
#Description-Functions for generating patterns.

import adsk.core, adsk.fusion, traceback, math, random

# Generate a sprial cube
# @arg countPoints = 20
# @arg angleDeg = 91
# @arg lengthGrow = 1
def generateSpiralCube(countPoints, angleDeg, lengthGrow):

    lineLength = 1
    points = []

    dirVec = adsk.core.Vector3D.create(1,0,0)
    ptLast = adsk.core.Point3D.create(0,0,0)
    points.append(ptLast)

    mat = adsk.core.Matrix3D.create()

    for i in range(countPoints - 1):
        
        ptNext = adsk.core.Point3D.create(ptLast.x + (lineLength * dirVec.x), ptLast.y + (lineLength * dirVec.y), 0)
        points.append(ptNext)

        ptLast = ptNext

        mat.setToRotation(angleDeg/180*math.pi, adsk.core.Vector3D.create(0,0,1), adsk.core.Point3D.create(0,0,0))
        dirVec.transformBy(mat)

        lineLength = lineLength + lengthGrow

    return [points]

# Generate a sprial cube
# @arg numArms = 10
# @arg numPointsPerArm = 20
# @arg armsOffset = 3
# @arg rateExpansion = 3
# @arg rateExpansion = 0.5
def generateSpiral(numArms = 10, numPointsPerArm = 20, armsOffset = 3, rateExpansion = 5, zStep = 0):

    lines = []

    for iArm in range(numArms):
        points = []
        pZ = 0

        for iPt in range(numPointsPerArm):
            pX = rateExpansion * iPt * math.cos(iPt + (math.pi * iArm)) + (random.random() * armsOffset)
            pY = rateExpansion * iPt * math.sin(iPt + (math.pi * iArm)) + (random.random() * armsOffset)
            if zStep != 0:
                pZ += zStep * random.random()

            pt3D = adsk.core.Point3D.create(pX, pY, pZ)
            points.append(pt3D)

        lines.append(points)
    
    return lines

