# -*- coding: utf-8 -*-
"""
/***************************************************************************
 TidyCity
                                 A QGIS plugin
 A simple QGIS python plugin for building tidy cities.
                              -------------------
        begin                : 2016-11-30
        git sha              : $Format:%H$
        copyright            : (C) 2016 - 2018 by IGN
        email                : julien.perret@gmail.com; mickael.brasebin@ign.fr
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/

"""

from PyQt5.QtGui import QTransform
from qgis.core import QgsField, QgsGeometry, QgsPointXY, QgsRectangle,  QgsWkbTypes
import math
import numpy
from statistics import *

"""
SMBR computation.
"""
def normalizedAngle(angle):
    clippedAngle = angle
    if ( clippedAngle >= math.pi * 2 or clippedAngle <= -2 * math.pi ):
        clippedAngle = math.fmod( clippedAngle, 2 * math.pi)
    if ( clippedAngle < 0.0 ):
        clippedAngle += 2 * math.pi
    return clippedAngle

def lineAngle(x1, y1, x2, y2):
    at = math.atan2( y2 - y1, x2 - x1 )
    a = -at + math.pi / 2.0
    return normalizedAngle( a )

def compute_SMBR(geom):
    area = float("inf")
    angle = 0
    width = float("inf")
    height =  float("inf")
    if (geom is None):
        return  QgsGeometry()
    hull = geom.convexHull()
    if ( hull.isEmpty() ):
        return QgsGeometry()
    x = hull.asPolygon()
    vertexId = 0
    pt0 = x[0][vertexId]
    pt1 = pt0
    prevAngle = 0.0
    size = len(x[0])
    for vertexId in range(0,  size-0):
        pt2 = x[0][vertexId]
        currentAngle = lineAngle( pt1.x(), pt1.y(), pt2.x(), pt2.y() )
        rotateAngle = 180.0 / math.pi *  (currentAngle - prevAngle)
        prevAngle = currentAngle
        t = QTransform.fromTranslate( pt0.x(), pt0.y() )
        t.rotate(rotateAngle)
        t.translate( -pt0.x(), -pt0.y() )
        hull.transform(t)
        bounds = hull.boundingBox()
        currentArea = bounds.width() * bounds.height()
        if ( currentArea  < area ):
            minRect = bounds
            area = currentArea
            angle = 180.0 / math.pi * currentAngle
            width = bounds.width()
            height = bounds.height()
        pt2 = pt1
    minBounds = QgsGeometry.fromRect( minRect )
    minBounds.rotate( angle, QgsPointXY( pt0.x(), pt0.y() ) )
    if ( angle > 180.0 ):
        angle = math.fmod( angle, 180.0 )
    return minBounds, area, angle, width, height

def m(c,i,g):
    attr = c.attribute(i)
    area = c.geometry().intersection(g).area()
    return (attr,area)

def find_areas(geom, index, dictionary, idAttribute):
    return [m(candidate, idAttribute, geom)
            for candidate in
            map(lambda id:dictionary[id], index.intersects(geom.boundingBox()))
            if candidate.geometry().intersects(geom)]

def findIRIS_line(geom,layer_IRIS,nom_idIRIS):
    intersections = []
    for iris in layer_IRIS.getFeatures():
        if iris.geometry().intersects(geom):
            intersections.append([iris.attribute(nom_idIRIS),iris.geometry().intersection(geom).length()])
    iris_id = 0
    length_max = 0
    for element in intersections:
        if element[1]>length_max:
            iris_id = element[0]
            length_max = element[1]
    return iris_id


def findIRIS(geom,layer_IRIS,nom_idIRIS):
    intersections = findIRIS_areas(geom,layer_IRIS,nom_idIRIS)
    iris_id = 0
    aire_max = 0
    for element in intersections:
        if element[1]>aire_max:
            iris_id = element[0]
            aire_max = element[1]
    return iris_id

def find(geom, index, dictionary, idAttribute):
    intersections = find_areas(geom, index, dictionary, idAttribute)
    return max(intersections, key=lambda x: x[1])[0]

def distance_from_polygon_to_layer(geom, index, dictionary, layer_id):
    #Centroid of input buildings
    point = geom.pointOnSurface().asPoint()
    #Cprint(point.asWkt())   
    distance = dictionary[index.nearestNeighbor(point,1)[0]].geometry().distance(geom)

    #Cprint(distance)
    bbox = geom.buffer(distance*1.5,3).boundingBox()
    #Cprint(bbox.asWktPolygon())
    
    return min(
        ((f.geometry().distance(geom), f.attribute(layer_id))
         for f in map(lambda id: dictionary[id], index.intersects(bbox))),
        key=lambda x: x[0])

def compute_elongation(d1, d2):
    """
    Calcul de l'élongation.
    """
    elongation = min(d1,d2)/max(d1,d2)
    return elongation

def compute_compactness(area, perimeter):
    """
    Calcul de la compacité.
    """
    return 4 * math.pi * area / (perimeter * perimeter)


def complexityPolygon(geom):
    
    
    return len(geom)-1

def compute_complexity(geom):
    type = geom.wkbType()
    if (type ==  QgsWkbTypes.MultiPolygon): # new part for multipolylines
        multiP = geom.asMultiPolygon()
        count = 0
        for v in multiP:
            count = count + complexityPolygon(v)
        return count
    elif (type == QgsWkbTypes.Polygon):
        polygon =  geom.asPolygon()
        count = 0
        for v in polygon :
            count = count + complexityPolygon(v)
        return count
    
    return 0

def compute_convexity1(geom, area):
    """
    Calcul de la convexité selon l'enveloppe convexe.
    """
    convexhull = geom.convexHull()
    convexity1 = area/convexhull.area()
    return convexity1

def compute_convexity2(area, SMBR_area):
    """
    Calcul de la convexité selon le SMBR.
    """
    convexity2 = area/SMBR_area	
    return convexity2

def compute_formFactor(hauteur, SMBR_width, SMBR_height):
    """
    Calcul du facteur de forme
    """
    formFactor = 2*hauteur/(SMBR_width+SMBR_height)
    return formFactor

def compute_formIndice(hauteur, area):
    """
    Calcul de l'indice de forme
    """
    formIndice = hauteur**2 / area
    return formIndice


