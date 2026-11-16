' SPDX-License-Identifier: MPL-2.0
Sub Main
Dim doc As Object, page As Object, first As Object, second As Object, navigation As Object, illustration As Object
Dim graphicProps(0) As New com.sun.star.beans.PropertyValue
Dim point As New com.sun.star.awt.Point
Dim size As New com.sun.star.awt.Size
Dim props(0) As New com.sun.star.beans.PropertyValue
Dim channel As Integer, kind As String, stem As String
Dim fixtureRoot As String
fixtureRoot = Environ("ODFA11Y_FIXTURE_ROOT")
channel = FreeFile
Open fixtureRoot & "/authoring.log" For Output As #channel
On Error GoTo Failure
props(0).Name = "Hidden"
props(0).Value = True
For Each kind In Array("simpress", "sdraw")
doc = StarDesktop.loadComponentFromURL("private:factory/" & kind, "_blank", 0, props())
page = doc.DrawPages.getByIndex(0)
Do While page.Count > 0
page.remove(page.getByIndex(0))
Loop
page.Name = "Fruit overview"
Print #channel, kind & " page properties"
For Each item In page.getPropertySetInfo().getProperties()
If item.Name = "Title" Or item.Name = "Description" Or item.Name = "NavigationOrder" Then Print #channel, item.Name
Next item
first = doc.createInstance("com.sun.star.drawing.TextShape")
point.X = 2000
point.Y = 2000
size.Width = 16000
size.Height = 2000
first.setPosition(point)
first.setSize(size)
page.add(first)
first.Name = "Overview title"
first.String = "Fruit overview"
second = doc.createInstance("com.sun.star.drawing.RectangleShape")
point.X = 3000
point.Y = 6000
size.Width = 7000
size.Height = 4000
second.setPosition(point)
second.setSize(size)
page.add(second)
second.Name = "Fruit box"
second.String = "Apples 3; Pears 4"
second.Title = "Fruit quantities"
second.Description = "Three apples and four pears"
illustration = doc.createInstance("com.sun.star.drawing.GraphicObjectShape")
point.X = 12000
point.Y = 6000
size.Width = 4000
size.Height = 4000
illustration.setPosition(point)
illustration.setSize(size)
page.add(illustration)
illustration.Name = "Fruit illustration"
graphicProps(0).Name = "URL"
graphicProps(0).Value = ConvertToURL(fixtureRoot & "/fruit.svg")
illustration.Graphic = CreateUnoService("com.sun.star.graphic.GraphicProvider").queryGraphic(graphicProps())
navigation = CreateUnoService("com.sun.star.drawing.ShapeCollection")
navigation.add(second)
navigation.add(first)
navigation.add(illustration)
page.NavigationOrder = navigation
If kind = "simpress" Then
stem = "presentation"
Else
stem = "drawing"
End If
doc.DocumentProperties.Title = "Fruit overview"
doc.DocumentProperties.Author = "ODFA11y fixture"
doc.storeAsURL(ConvertToURL(fixtureRoot & "/fruit-" & stem & IIf(kind = "simpress", ".odp", ".odg")), Array())
Print #channel, stem & " saved"
doc.close(True)
Next kind
GoTo Finish
Failure:
Print #channel, "error " & Err & ": " & Error$
Finish:
Close #channel
StarDesktop.terminate()
End Sub
