from mojo.events import EditingTool, BaseEventTool, installTool, addObserver, removeObserver, extractNSEvent
import mojo.drawingTools as dt
from mojo.UI import getGlyphViewDisplaySettings, setGlyphViewDisplaySettings, CurrentGlyphWindow
from lib.tools.defaults import getDefaultColor, getDefault
from mojo.extensions import ExtensionBundle

"""
Blue Zone Editor
by Andy Clymer, October 2018

"""



BLUEKEYS = ["postscriptBlueValues", "postscriptOtherBlues"]

c = getDefaultColor("glyphViewSelectionMarqueColor")
MARQUECOLOR = (c.redComponent(), c.greenComponent(), c.blueComponent(), c.alphaComponent())

c = getDefaultColor("glyphViewBluesColor")
BLUESCOLOR = (c.redComponent(), c.greenComponent(), c.blueComponent(), c.alphaComponent())

VIEWWIDTH = getDefault("glyphViewDefaultWidth")


    
class BlueZone(object):
    
    """
    Manages a pair of blue zone locations as one solid zone
    Has helper functions for selecting zone edges and moving the selection
    """
    
    def __init__(self, startPosition, endPosition, isOther=False):
        self.startPosition = startPosition
        self.startSelected = False # and the mouse offset if it is selected
        self.endPosition = endPosition
        self.endSelected = False # and the mouse offset if it is selected
        self.isOther = isOther
    
    def __repr__(self):
        if self.isOther:
            return "<BlueZone (Other) %s %s>" % (self.startPosition, self.endPosition)
        else: return "<BlueZone %s %s>" % (self.startPosition, self.endPosition)
        
    def moveSelection(self, delta):
        xOffset, yOffset = delta
        if self.startSelected:
            self.startSelected += xOffset
            self.startPosition -= yOffset
        if self.endSelected:
            self.endSelected += xOffset
            self.endPosition -= yOffset
        # Keep the start lower than the end
        if self.startPosition > self.endPosition:
            self.startPosition, self.endPosition = self.endPosition, self.startPosition
            # And move the selection
            if self.startSelected and not self.endSelected:
                self.startSelected = False
                self.endSelected = True
            elif self.endSelected and not self.startSelected:
                self.startSelected = True
                self.endSelected = False
        self.startPosition = int(round(self.startPosition))
        self.endPosition = int(round(self.endPosition))
            
    @property
    def selected(self):
        return self.startSelected or self.endSelected
    
    def deselect(self):
        self.startSelected = False
        self.endSelected = False
    
    def select(self, point):
        # Select whichever edge is closest to the point location
        self.startSelected = False
        self.endSelected = False
        if abs(self.startPosition - point[1]) < abs(self.endPosition - point[1]):
            self.startSelected = point[0]
        else: self.endSelected = point[0]
        
    def distance(self, location):
        # Return the distance to either edge (whichever is closest) to the point
        distances = [abs(self.startPosition - location), abs(self.endPosition - location)]
        distances.sort()
        return distances[0]
        
    def pointInside(self, location):
        positions = [self.startPosition, self.endPosition]
        positions.sort()
        if positions[0] < location < positions[1]:
            return True
        else: return False
        
    def draw(self, scale):
        dt.save()
        # Draw the zone
        dt.fill(*BLUESCOLOR)
        dt.stroke(None)
        dt.rect(-1*VIEWWIDTH*scale, self.startPosition, VIEWWIDTH*2*scale, self.endPosition-self.startPosition)
        # See if any edges are selected
        selectedPoints = []
        if self.startSelected:
            selectedPoints += [(self.startSelected, self.startPosition)]
        if self.endSelected:
            selectedPoints += [(self.endSelected, self.endPosition)]
        # Shade in the zone if it's selected
        if len(selectedPoints):
            dt.fill(*MARQUECOLOR)
            dt.stroke(None)
            dt.rect(-1*VIEWWIDTH*scale, self.startPosition, VIEWWIDTH*2*scale, self.endPosition-self.startPosition)
        # Draw the zone type
        if self.isOther:
            dt.stroke(None)
            dt.fill(1, 1, 1, 1)
            bottom, top = self.startPosition+10, self.startPosition
        else: 
            dt.stroke(None)
            dt.fill(0.2, 0.2, 0.8, 1)
            bottom, top = self.endPosition-10, self.endPosition
        dt.newPath()
        dt.moveTo((0, top))
        dt.lineTo((-5, bottom))
        dt.lineTo((5, bottom))
        dt.closePath()
        dt.drawPath()
        dt.restore()
        # Draw a stroke on the selected zone edges
        dt.fill(None)
        dt.stroke(r=0, g=0, b=1, a=0.5)
        dt.strokeWidth(3*scale)
        for selectedPoint in selectedPoints:
            dt.newPath()
            dt.moveTo((-30, selectedPoint[1]))
            dt.lineTo((30, selectedPoint[1]))
            dt.drawPath()
        # Draw the zone locations and its type
        if len(selectedPoints):
            dt.fill(r=0, g=0, b=1, a=0.5)
            dt.stroke(None)
            positions = [self.startPosition, self.endPosition]
            positions.sort()
            dt.font("LucidaGrande-Bold")
            dt.fontSize(12 * scale)
            size = dt.textSize(str(0), align=None)
            zoneHeight = positions[1] - positions[0]
            if zoneHeight < 10:
                offset = 10 - zoneHeight
            else: offset = 0
            dt.textBox(str(positions[0]), (-100, positions[0]-size[1]-offset, 200, size[1]), align="center")
            dt.textBox(str(positions[1]), (-100, positions[1], 200, size[1]+(2*scale)), align="center")
            # Write the name type
            if self.isOther:
                typeText = "OtherBlue"
            else: typeText = "BlueValue"
            dt.textBox(typeText, (-100, positions[1], 200, size[1]*2), align="center")
        dt.fill(None)
        dt.stroke(None)



class BlueEdit(BaseEventTool):
    
    def becomeActive(self):
        # Remember the current display settings, and turn the blues off (I'll draw them myself)
        self.previousDisplaySettings = {"Blues": getGlyphViewDisplaySettings()["Blues"], "Family Blues": getGlyphViewDisplaySettings()["Family Blues"]}
        setGlyphViewDisplaySettings({"Blues":False, "Family Blues":False})
        # Attributes
        self.font = CurrentFont()
        self.zones = []
        self.currentlyUpdatingInfo = False
        
        # Start tracking the CurrentFont (if there is one)
        self.fontChangedCallback(None)
        # Observers
        addObserver(self, "fontChangedCallback", "fontBecameCurrent")
    
    
    def becomeInactive(self):
        # Reset the display settings
        setGlyphViewDisplaySettings(self.previousDisplaySettings)
        # Observers
        removeObserver(self, "fontBecameCurrent")
        if not self.font == None:
            self.applyZones()
            self.font.info.removeObserver(self, "Info.Changed")


    def getToolbarIcon(self):
        extBundle = ExtensionBundle("BlueZoneEditor")
        toolbarIcon = extBundle.get("BlueZoneToolIcon-2x")
        return toolbarIcon

    def getToolbarTip(self):
        return "Blue Zones"
        
        
    # Observer callbacks
        
    def fontChangedCallback(self, info):
        # Forget any font-specific settings and observe on the font info
        cf = CurrentFont()
        # If there really is a new font
        if not self.font == cf:
            # If there was an old font
            if not self.font == None:
                # Apply the zones before switching
                self.applyZones()
                self.font.info.removeObserver(self, "Info.Changed")
            self.font = cf
            if not self.font == None:
                self.font.info.addObserver(self, "infoChanged", "Info.Changed")
        if not self.font == None:
            self.collectZones()
        
        
    def infoChanged(self, info):
        # The font info changed
        # Cache the blue zone data because it may have changed,
        # but only if this tool is not currently editing the font info.
        if not self.currentlyUpdatingInfo:
            self.collectZones()
    
    
    def mouseDown(self, point, count):
        yLoc = int(round(point[1]))
        if count == 2:
            # Double click in a zone: flip it between "blues" and "otherBlues"
            didFlipZone = False
            for zone in self.zones:
                if zone.pointInside(yLoc):
                    didFlipZone = True
                    zone.isOther = not zone.isOther
            if not didFlipZone:
                # Double click not on a zone: add a new zone
                self.addZone(yLoc-5, yLoc+5)
        elif count == 1:
            # Single click: find the closest zone *edge* in a range and select it
            selected = self.selectClosestZoneEdge((point.x, point.y))
            if not selected:
                # Didn't select an edge, select both edges if the click happened within a zone
                for zone in self.zones:
                    if zone.pointInside(yLoc):
                        zone.startSelected = True
                        zone.endSelected = True
            
            
    def mouseDragged(self, point, delta):
        # If the mouse is dragging, move selected zones
        for zone in self.zones:
            zone.moveSelection(delta)
    
    
    def mouseUp(self, point):
        # If any zones are selected, update the font info, they may have changed
        wasSelected = False
        for zone in self.zones:
            if zone.selected:
                wasSelected = True
        if wasSelected:
            self.applyZones()
    
    
    def keyDown(self, event):
        e = extractNSEvent(event)
        # Arrow keys to move
        moveValue = 0
        if ord(e["keyDown"]) == 63232: # Up
            if e["shiftDown"]:
                moveValue = -10
            else: moveValue = -1
        elif ord(e["keyDown"]) == 63233: # Down
            if e["shiftDown"]:
                moveValue = 10
            else: moveValue = 1
        if moveValue:
            for zone in self.zones:
                zone.moveSelection((0, moveValue))
            self.redraw()
        # Delete to remove zones
        if ord(e["keyDown"]) == 127: # Delete
            self.removeSelectedZones()
        # Return to flip zones
        if ord(e["keyDown"]) == 13: # Return
            for zone in self.zones:
                if zone.selected:
                    zone.isOther = not zone.isOther
            self.redraw()
            
        
    def draw(self, scale):
        for zone in self.zones:
            zone.draw(scale)
                
        
    
    # Helpers
        
        
    def redraw(self):
        cgw = CurrentGlyphWindow()
        cgw.getGlyphView().refresh()
    
    
    def collectZones(self):
        self.zones = []
        for k in BLUEKEYS:
            isOther = False
            if "Other" in k:
                isOther = True
            zoneValues = getattr(self.font.info, k)
            for i in range(0, len(zoneValues), 2):
                z = BlueZone(zoneValues[i], zoneValues[i+1], isOther=isOther)
                self.zones += [z]

    
    def applyZones(self):
        for k in BLUEKEYS:
            isOther = False
            if "Other" in k:
                isOther = True
            newZoneRanges = []
            for zone in self.zones:
                if zone.isOther == isOther:
                    thisZoneRange = [int(round(zone.startPosition)), int(round(zone.endPosition))]
                    thisZoneRange.sort()
                    newZoneRanges.append(thisZoneRange)
            if len(newZoneRanges):
                # Sort and combine overlapping zones
                newZoneRanges.sort(key=lambda x: x[0])
                newZones = [list(newZoneRanges[0])]
                for z in newZoneRanges:
                    if z[0] < newZones[-1][1]:
                        if z[1] > newZones[-1][1]:
                            newZones[-1][1] = z[1]
                    else: newZones += [list(z)]
                # Flatten the pairs into a single list
                newZoneRanges = [int(round(v)) for r in newZones for v in r]
            # Apply
            self.currentlyUpdatingInfo = True
            self.font.info.prepareUndo("Zone change")
            setattr(self.font.info, k, newZoneRanges)
            self.font.info.performUndo()
            self.currentlyUpdatingInfo = False

    
    def selectClosestZoneEdge(self, point, keepSelection=False, distance=6):
        # Find the closest zone edge to the location and select it
        # Optionally, keep the current selection of zones
        if not self.font == None:
            closestZone = None
            closestDist = distance
            for zone in self.zones:
                if not keepSelection:
                    zone.deselect()
                thisDist = zone.distance(point[1])
                if thisDist < closestDist:
                    closestDist = thisDist
                    closestZone = zone
            if closestZone:
                closestZone.select(point)
                return True
        return False
                
                
    def countZones(self):
        # Return a count of the blues and otherBlues
        zoneCount = {"postscriptBlueValues": 0, "postscriptOtherBlues": 0}
        for zone in self.zones:
            if zone.isOther:
                zoneCount["postscriptOtherBlues"] += 1
            else: zoneCount["postscriptBlueValues"] += 1
        return zoneCount
        
        
    def addZone(self, startPos, endPos, isOther=False):
        if isOther:
            blueKey = "postscriptOtherBlues"
        else: blueKey = "postscriptBlueValues"
        if not self.font == None:
            if self.countZones()[blueKey] < 7:
                z = BlueZone(startPos, endPos, isOther=isOther)
                z.startSelected = True
                z.endSelected = True
                self.zones += [z]
                
    
    def removeSelectedZones(self):
        newZones = []
        for zIdx, zone in enumerate(self.zones):
            if not zone.selected:
                newZones.append(zone)
        self.zones = newZones
        self.applyZones()
    
    
    def flipSelectedZone(self, index):
        for zone in self.zones:
            if zone.selected:
                zone.isOther = not zone.isOther
    
    

installTool(BlueEdit())