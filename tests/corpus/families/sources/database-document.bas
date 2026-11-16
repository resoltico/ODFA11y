' SPDX-License-Identifier: MPL-2.0
Sub Main
Dim doc As Object, connection As Object, statement As Object, query As Object, queries As Object
Dim channel As Integer
Dim fixtureRoot As String
fixtureRoot = Environ("ODFA11Y_FIXTURE_ROOT")
channel = FreeFile
Open fixtureRoot & "/database-authoring.log" For Output As #channel
On Error GoTo Failure
doc = CreateUnoService("com.sun.star.sdb.OfficeDatabaseDocument")
doc.DataSource.URL = "sdbc:embedded:firebird"
doc.storeAsURL(ConvertToURL(fixtureRoot & "/fruit-database.odb"), Array())
connection = doc.DataSource.getConnection("", "")
statement = connection.createStatement()
statement.executeUpdate("CREATE TABLE ""Fruit"" (""Item"" VARCHAR(30), ""Count"" INTEGER)")
statement.executeUpdate("INSERT INTO ""Fruit"" VALUES ('Apples', 3)")
statement.executeUpdate("INSERT INTO ""Fruit"" VALUES ('Pears', 4)")
connection.close()
doc.store()
Print #channel, "database saved"
doc.dispose()
GoTo Finish
Failure:
Print #channel, "error " & Err & ": " & Error$
Finish:
Close #channel
StarDesktop.terminate()
End Sub
