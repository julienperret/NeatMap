from PyQt5.QtCore import QVariant
from .morpho import *
from qgis.core import *


"""
Structures and convention used in the code

Variable named : boundingBox (QGSFeatureList, width, height, area)
Variable named : rectangle (QGSFeatureList, x, y, width, height, area) 
Variable named : vertex (x,y)

"""






"""
Layout methods
"""



#Basic method : 1 line by class
def naive_layout(vectorLayer, attributeClass, secondaryRankingAttribute, outputLayerName):
    #Transforming feature to rectangles on a same line
    boundingBox_tuples = initialise_layout(vectorLayer, attributeClass, secondaryRankingAttribute, outputLayerName)
    #Initializing new layer
    vl = QgsVectorLayer("Polygon", outputLayerName, "memory")
    pr = vl.dataProvider()
    #Getting fields for the layer (the feature are initialized)
    fields = [vectorLayer.fields().field(attributeClass), vectorLayer.fields().field(secondaryRankingAttribute)]
    #Update
    pr.addAttributes(fields)
    vl.updateFields()
    #List of feature for the vectorlayer
    featureList = []
    #We only apply a y translation on the rectangle
    current_y = 0
    #For each rectangle
    for boundingBox in boundingBox_tuples:
        #We get the list of corresponding feature
        featureListTemp = boundingBox[0]
        #We translate the geometry and update current_y
        for feature in featureListTemp:
            geometry = feature.geometry()
            geometry.translate(0, current_y +  boundingBox[2]/2 )
            feature.setGeometry(geometry)
            featureList.append(feature)
        current_y = current_y + boundingBox[2]
        
    #Commit changes
    pr.addFeatures(featureList)
    vl.commitChanges()

    return vl
    

def advanced_layout(vectorLayer, attributeClass, secondaryRankingAttribute, outputLayerName):
    #1- We generate a basic layout with no placement (1 bounding box = 1 class)
    boundingBox_tuples =  initialise_layout(vectorLayer, attributeClass, secondaryRankingAttribute, outputLayerName)
    #2 - Determining the possible bounding boxes ordered by area
    minimumBoundingBoxes = minimumBoundingBox(boundingBox_tuples)
    #2 - Packing the bounding box into the minimumBounding box with smallest area
    rectngle_tuple = pack(boundingBox_tuples, minimumBoundingBoxes)
    # can be transformed into VectorLayer with => fromPlaceRectangleToVectorLayer(rectngle_tuple)
    #3 - Displacing the geographic feature 
    vl = movingFeature(rectngle_tuple, vectorLayer, attributeClass, secondaryRankingAttribute, outputLayerName )
    return vl,  fromPlaceRectangleToVectorLayer(rectngle_tuple)


"""
Secondary methods
"""


#Basic method that generates the bounding box for the different classes
#Rotate the feature according to their orientation
#
def initialise_layout(vectorLayer, attributeClass, secondaryRankingAttribute, outputLayerName):
    # provide file name index and field's unique values
    fni = vectorLayer.fields().indexFromName(attributeClass)
    unique_values = vectorLayer.uniqueValues(fni)
    fields = [vectorLayer.fields().field(attributeClass), vectorLayer.fields().field(secondaryRankingAttribute)]

    #That tuples contain bounding boxes
    #(1) a feature list for a given class 
    #(2) the width of the rectangle of the class
    #(3) the height of the rectangle of the class
    #(4) the area of the rectangle of the class (3 * 2)
    boundingBox_tuples = []
    
    #For each class
    for val in unique_values:
        #We list the features of the class
        featureList = []

        #The features corresponding to the class are selected and ordered by secondaryRankingAttribute
        expr = QgsExpression( "\""+str(attributeClass)+"\"="+str(val))
        request = QgsFeatureRequest( expr)
        request = request.addOrderBy("\""+str(secondaryRankingAttribute)+"\"",False)
        it = vectorLayer.getFeatures(request)
        #The x of the current feature
        x_current = 0
  
        #The heighest bow is necessary to shift the next line
        heighestBox = 0;
        
        for featCurrent in it :
           # print("Valeurs : class value " + str(featCurrent.attribute(attributeClass)) + "  secondary value" + str(featCurrent.attribute(secondaryRankingAttribute)))
            geom = featCurrent.geometry()
            #We determine box of the current geometry
            minBounds, area, angle, width, height = compute_SMBR(geom)
            #The centroid of the box
            centroid = minBounds.centroid().asPoint()
            
            #We check that the 
            if(width > height) :
                angle = angle + 90
                width, height = height, width
            
            #Rotate of the geometry according to SMBR angle
            err = geom.rotate( -angle, centroid)

            
            #Determining the translation into a local referential
            dx = x_current - centroid.x() + width/2.0
            dy = - centroid.y()

            heighestBox = max(heighestBox, height)
            
            x_current = x_current + (width)
           
            err = geom.translate(dx,dy)

            #We create a feature with the fields and the transformed geometry
            new_feature = QgsFeature()
            new_feature.setGeometry(geom)
            new_feature.initAttributes(len(fields))
            new_feature.setAttribute(0, featCurrent.attribute(attributeClass))
            new_feature.setAttribute(1, featCurrent.attribute(secondaryRankingAttribute))

            featureList.append(new_feature)
            
        """
        if x_current < heighestBox :
            x_current, heighestBox = heighestBox, x_current
            
            
            #If there is a rotation features must move
            for featCurrent in featureList :
                geom = featCurrent.geometry()
                #We determine box of the current geometry
                minBounds, area, angle, width, height = compute_SMBR(geom)
                #The centroid of the box
                centroid = minBounds.centroid().asPoint()
                geom.rotate( 90, centroid)
                #We inverse x et y
                dx = centroid.y() - centroid.x()
                dy = centroid.x() - centroid.y()
                geom.translate(dx,dy)
                featCurrent.setGeometry(geom)
             
            """
        
        
        #The rectangle is added to the tuple
        boundingBox_tuples.append([featureList, x_current, heighestBox, x_current * heighestBox])

    return boundingBox_tuples

#Determine all the candidate bounding boxes sorted by area
def minimumBoundingBox(boundingBox_tuple):
    # Testing all boxes in increasing order and keep the  smallest

    #Lower bound : sum of the areas of the given boundingBox
    #Upper bound  : greedy method : highest boundingBox and all the boundingBoxs
    lowerArea = 0;
    totalWidth = 0 ;
    heighestBox = 0;
    widestBox = 0
    
    for boundingBox in boundingBox_tuple:
        lowerArea = lowerArea + boundingBox[3]
        totalWidth = totalWidth + boundingBox[1]
        heighestBox = max(heighestBox, boundingBox[2])
        widestBox = max(widestBox, boundingBox[1])
    upperArea = totalWidth * heighestBox
  
    
    nb_BoundingBox = len(boundingBox)
    
    possibleHeight = []
    possibleWidth = []
    
    
    for i in range(1, nb_BoundingBox+1) :
        
        for rectangle in combinaison(boundingBox_tuple, i):
            widthSum = 0
            heightSum = 0
            for r in rectangle:
                widthSum = widthSum + r[1]
                heightSum = heightSum + r[2]


            possibleHeight.append(heightSum)
            possibleWidth.append(widthSum)

    
    #All possible width and height
    possibleHeight = sorted(possibleHeight)
    possibleWidth = sorted(possibleWidth)

    #Width, height, area
    boundingBox = []
    
    for width in possibleWidth :
        #The width  must  be at least the height of the tallest rectangle
        if width < widestBox :
            continue
        
        #The height must  be at least the height of the tallest rectangle
        for height in possibleHeight:
            if height < heighestBox:
                continue
            
            #The area must be enough to contain all rectangles
            area = width * height
            if area < lowerArea:
                continue
            
            if area > upperArea:
                continue
            
            boundingBox.append([None, width, height, area])

    resultSorted = sorted(boundingBox, key=lambda tup: tup[3])
    # print(resultSorted)
    return resultSorted

    
    
#Try to pack the bounding box into the candidate bounding boxes
def pack(boundingBox_tuples, boundingBoxes):
    
    
    for b in boundingBoxes :
            layout = determineLayout(boundingBox_tuples, b)
            if not layout is None:
                break

    return layout
    
#Generate a layout relatively to a bounding box
#Placement is organized from widest  
def determineLayout(boundingBox_tuples, boundingBox):
    boundingBox_tuples = sorted(boundingBox_tuples, key=lambda tup: tup[1], reverse=True)
    #X,Y coordinates
    #Originate is lower left point
    possibleVertices = [(0,0)]
    #feature, X,Y,Width,Length, area
    #Originate is lower left point
    placedRectangles = []
    #When a new placed rectangle generate a non-reflex vertex
    #A supplementary vertice may be generated under it 
    # Either at y = 0 or at the first met box under it
    suppVertix = None
    
    #For each boxes
    for boundingBoxToPlace in boundingBox_tuples :
        #A place is not found
        isPlaced = False
        #We test all the candidate vertices
        for vertix in possibleVertices :
            #Can we place the rectangle at a given vertex
            #Without intersecting the other ?
            rectangleOk = canPlaceRectangle(vertix, boundingBoxToPlace,placedRectangles)
            if rectangleOk is None:
                continue
            #Is it in the input bounding box
            if not checkIfIsBoundingBox(rectangleOk, boundingBox):
                continue
            #Yes we keep the position
            isPlaced = True
            #We determine if a supplementaryVertix is necessary
            suppVertix = supplementaryVertix([vertix[0] + boundingBoxToPlace[1], vertix[1]], placedRectangles)
            #Append to placed rectangles
            placedRectangles.append(rectangleOk)
            #we do not need to continue
            break;
        if not isPlaced:
            #It means that the bounding box cannnot be placed
            #The algo is stopped and a new layout will be tested
            #With an other constraint bounding box
            return None;
        #We remove the current vertex
        possibleVertices.remove(vertix)
        #If there is a supplementary vertex, we will use it
        if not suppVertix is None:
            possibleVertices.append(suppVertix)
        
        possibleVertices.append([vertix[0] + boundingBoxToPlace[1], vertix[1]])
        
        possibleVertices.append([vertix[0], vertix[1] + boundingBoxToPlace[2]])
            
        
        possibleVertices.append([vertix[0] + boundingBoxToPlace[1], vertix[1] + boundingBoxToPlace[2]])
        
   
        #Reordering vertices according to origin distance
        possibleVertices = sorted(possibleVertices, key=lambda x: (x[1] * x[1] + x[0] * x[0]))
    
    
    
    return placedRectangles




def  movingFeature(rectngle_tuple,  vectorLayer,  attributeClass, secondaryRankingAttribute, outputLayerName):
    #Initializing new layer
    vl = QgsVectorLayer("Polygon", outputLayerName, "memory")
    pr = vl.dataProvider()
    #Getting fields for the layer (the feature are initialized)
    fields = [vectorLayer.fields().field(attributeClass), vectorLayer.fields().field(secondaryRankingAttribute)]
    #Update
    pr.addAttributes(fields)
    vl.updateFields()
    
    features = []
    
    for rectangle in rectngle_tuple:
        #The translation is encoding with X,Y
        x = rectangle[1]
        y = rectangle[2] + rectangle[4] /2
        
        for feature in rectangle[0]:
            geometry = feature.geometry()
            geometry.translate(x,y)
            feature.setGeometry(geometry)
            features.append(feature)
            

    pr.addFeatures(features)
    vl.commitChanges()
    return vl
"""
Utility functions
"""

#Assesing combinaison from a tuple
def combinaison(seq, k):
    p = []
    i, imax = 0, 2**len(seq)-1
    while i<=imax:
        s = []
        j, jmax = 0, len(seq)-1
        while j<=jmax:
            if (i>>j)&1==1:
                s.append(seq[j])
            j += 1
        if len(s)==k:
            p.append(s)
        i += 1 
    return p


#Determine if a rectangle can be placed at a given vertex (i.e if it does not intersects other placed rectangles)
def canPlaceRectangle(vertix, rectangle,placedRectangles):
    rectangleToTest = (rectangle[0], vertix[0], vertix[1], rectangle[1], rectangle[2], rectangle[3])
    for placeRectangle in placedRectangles:
        intersected = testIntersection(rectangleToTest, placeRectangle)
        if intersected :
            return None;
        
    return rectangleToTest

#Check if a rectangle is inside a bounding box
def checkIfIsBoundingBox(placedRectangle, boundingBox):
    return (placedRectangle[1] + placedRectangle[3] <= boundingBox[1]) and (placedRectangle[2] + placedRectangle[4] <= boundingBox[2])

#Test the intersection between two rectangles
def testIntersection(r1,r2):
    
    if ((r1[1] < (r2[1] + r2[3])) and (r2[1] < (r1[1]+r1[3])) and
     (r1[2] < (r2[2] + r2[4])) and (r2[2] < (r1[2]+r1[4]))):
           return True
    return False   

#Eventually add a supplementary vertix in the cas of non-reflex vertex
#If a box is added
def supplementaryVertix(vertixIni, placedRectangles):
    if(vertixIni[1] == 0):
        return None
    
    newY =  0;
    #We only keep the y with the highest value (if not above the rectangle)
    for rectangles in placedRectangles:
        if( (rectangles[1] < vertixIni[0]) and (rectangles[1] + rectangles[3] > vertixIni[0])):
            currentY = rectangles[2] + rectangles[4]
            
            if(vertixIni[1] < currentY):
                continue;
            
            newY = max(newY, currentY)
            
    #print("New y :" + str(newY))
    return [vertixIni[0], newY]
    

    
 


"""
Transforming intermediate objects to VectorLayer
"""

def fromPlaceRectangleToVectorLayer(placedRectangle):
    features = []
    
    fields = [QgsField("X", QVariant.Double),QgsField("Y", QVariant.Double), QgsField("width", QVariant.Double),QgsField("height", QVariant.Double)]
    vl = QgsVectorLayer("Polygon", "temp", "memory")
    pr = vl.dataProvider()
    vl.startEditing()
    
    pr.addAttributes(fields)
    vl.updateFields()
    
    for b in placedRectangle:
            feat = generateBoundingBox(b[1], b[2], b[3], b[4], fields)
            features.append(feat)
            
    print("Number of features :" + str(len(features)))
    pr.addFeatures(features)
    vl.commitChanges()
    return vl


def fromBoundingBoxToVectorLayer(boundingBox):
    features = []
    
    fields = [QgsField("width", QVariant.Double),QgsField("height", QVariant.Double)]
    vl = QgsVectorLayer("Polygon", "bob", "memory")
    pr = vl.dataProvider()
    vl.startEditing()
    
    pr.addAttributes(fields)
    vl.updateFields()
    
    for b in boundingBox:
            feat = generateBoundingBox(b[0], b[1], b[2])
            features.append(feat)
            
    print("Number of features :" + str(len(features)))
    pr.addFeatures(features)
    vl.commitChanges()
    return vl

            
def generateBoundingBox(x,y, width, height, fields):
    gPolygon = QgsGeometry.fromPolygonXY([[QgsPointXY(x, y), QgsPointXY(x+ width, y), QgsPointXY(x + width, y + height), 
                                           QgsPointXY(x, y +height)]])

    
    feat = QgsFeature()
    feat.setGeometry(gPolygon)
    feat.initAttributes(len(fields))
    
    feat.setAttribute(0, width)
    feat.setAttribute(1, height)
    return feat;