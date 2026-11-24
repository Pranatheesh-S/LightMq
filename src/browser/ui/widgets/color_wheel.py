"""Interactive hue ring and saturation/value surface for theme selection."""

from __future__ import annotations

import math

from PySide6.QtCore import Qt, Signal, QPointF, QRectF
from PySide6.QtGui import QColor, QConicalGradient, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget


class HueRingWidget(QWidget):
    """Clickable, draggable 360-degree hue ring."""

    hueChanged = Signal(int)

    def __init__(self, hue: int = 215, parent=None):
        super().__init__(parent)
        self.hue=max(0,min(359,int(hue)))
        self.setMinimumSize(118,118)
        self.setFixedSize(132,132)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName("Theme hue wheel")

    def setHue(self,hue:int)->None:
        self.hue=max(0,min(359,int(hue)));self.update()

    def paintEvent(self,event)->None:
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect=QRectF(7,7,self.width()-14,self.height()-14)
        gradient=QConicalGradient(rect.center(),-90)
        for degree in range(0,361,5):gradient.setColorAt(degree/360,QColor.fromHsv(degree%360,255,255))
        pen=QPen();pen.setWidthF(13);pen.setBrush(gradient);painter.setPen(pen);painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(rect.adjusted(8,8,-8,-8))
        angle=math.radians(self.hue-90);radius=(rect.width()-16)/2
        point=QPointF(rect.center().x()+math.cos(angle)*radius,rect.center().y()+math.sin(angle)*radius)
        painter.setPen(QPen(QColor("white"),3));painter.setBrush(QColor.fromHsv(self.hue,255,255));painter.drawEllipse(point,8,8)

    def _set_from_position(self,point)->None:
        center=QPointF(self.width()/2,self.height()/2)
        angle=(math.degrees(math.atan2(point.y()-center.y(),point.x()-center.x()))+90)%360
        self.hueChanged.emit(round(angle)%360)

    def mousePressEvent(self,event)->None:
        if event.button()==Qt.MouseButton.LeftButton:self._set_from_position(event.position())

    def mouseMoveEvent(self,event)->None:
        if event.buttons() & Qt.MouseButton.LeftButton:self._set_from_position(event.position())


class SaturationValueWidget(QWidget):
    """Two-dimensional color surface for saturation and brightness/value."""

    colorChanged=Signal(int,int)

    def __init__(self,hue:int=215,saturation:int=180,value:int=220,parent=None):
        super().__init__(parent)
        self.hue=hue;self.saturation=saturation;self.value=value
        self.setMinimumSize(170,132);self.setFixedSize(190,142)
        self.setCursor(Qt.CursorShape.CrossCursor);self.setAccessibleName("Theme saturation and brightness")

    def setHue(self,hue:int)->None:self.hue=hue;self.update()
    def setColor(self,saturation:int,value:int)->None:self.saturation=saturation;self.value=value;self.update()

    def paintEvent(self,event)->None:
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect=QRectF(1,1,self.width()-2,self.height()-2)
        painter.setPen(QPen(QColor("#647080"),1));painter.setBrush(QColor.fromHsv(self.hue,255,255));painter.drawRoundedRect(rect,8,8)
        sat=QLinearGradient(rect.topLeft(),rect.topRight());sat.setColorAt(0,QColor("white"));sat.setColorAt(1,QColor.fromHsv(self.hue,255,255))
        painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(sat);painter.drawRoundedRect(rect,8,8)
        shade=QLinearGradient(rect.topLeft(),rect.bottomLeft());shade.setColorAt(0,QColor(0,0,0,0));shade.setColorAt(1,QColor(0,0,0,255))
        painter.setBrush(shade);painter.drawRoundedRect(rect,8,8)
        point=QPointF(rect.left()+self.saturation/255*rect.width(),rect.top()+(255-self.value)/255*rect.height())
        painter.setPen(QPen(QColor("black"),3));painter.setBrush(Qt.BrushStyle.NoBrush);painter.drawEllipse(point,7,7)
        painter.setPen(QPen(QColor("white"),1.5));painter.drawEllipse(point,7,7)

    def _set_from_position(self,point)->None:
        x=max(1,min(self.width()-1,point.x()));y=max(1,min(self.height()-1,point.y()))
        saturation=round((x-1)/(self.width()-2)*255);value=255-round((y-1)/(self.height()-2)*255)
        self.colorChanged.emit(saturation,value)

    def mousePressEvent(self,event)->None:
        if event.button()==Qt.MouseButton.LeftButton:self._set_from_position(event.position())

    def mouseMoveEvent(self,event)->None:
        if event.buttons() & Qt.MouseButton.LeftButton:self._set_from_position(event.position())
