' SPDX-License-Identifier: MPL-2.0
Sub Main
Dim doc As Object
Dim channel As Integer
Dim fixtureRoot As String
fixtureRoot = Environ("ODFA11Y_FIXTURE_ROOT")
channel = FreeFile
Open fixtureRoot & "/chart-authoring.log" For Output As #channel
On Error GoTo Failure
doc = StarDesktop.loadComponentFromURL("private:factory/scalc", "_blank", 0, Array())
Dim sheet As Object
Dim rect As New com.sun.star.awt.Rectangle
Dim ranges(0) As New com.sun.star.table.CellRangeAddress
sheet = doc.Sheets.getByIndex(0)
sheet.getCellByPosition(0,0).String = "Item"
sheet.getCellByPosition(1,0).String = "Count"
sheet.getCellByPosition(0,1).String = "Apples"
sheet.getCellByPosition(1,1).Value = 3
sheet.getCellByPosition(0,2).String = "Pears"
sheet.getCellByPosition(1,2).Value = 4
rect.X = 3000
rect.Y = 3000
rect.Width = 12000
rect.Height = 8000
ranges(0).Sheet = 0
ranges(0).StartColumn = 0
ranges(0).StartRow = 0
ranges(0).EndColumn = 1
ranges(0).EndRow = 2
sheet.Charts.addNewByName("Fruit", rect, ranges(), True, True)
sheet.Charts.getByName("Fruit").EmbeddedObject.createInternalDataProvider(True)
doc.storeAsURL(ConvertToURL(fixtureRoot & "/fruit-chart-source.ods"), Array())
Print #channel, "chart spreadsheet saved"
doc.close(True)
GoTo Finish
Failure:
Print #channel, "error " & Err & ": " & Error$
Finish:
Close #channel
StarDesktop.terminate()
End Sub
