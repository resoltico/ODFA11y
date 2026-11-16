' SPDX-License-Identifier: MPL-2.0
Sub Main
Dim doc As Object
Dim props(0) As New com.sun.star.beans.PropertyValue
props(0).Name = "Hidden"
props(0).Value = True
doc = StarDesktop.loadComponentFromURL("private:factory/smath", "_blank", 0, props())
doc.Formula = "a + b = c"
doc.DocumentProperties.Title = "Invented sum relation"
doc.DocumentProperties.Author = "ODFA11y fixture"
doc.storeAsURL(ConvertToURL(Environ("ODFA11Y_FIXTURE_ROOT") & "/sum-formula.odf"), Array())
doc.close(True)
StarDesktop.terminate()
End Sub
