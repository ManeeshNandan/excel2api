from excel2api.reader import read_file


def test_read_excel():
    rows = read_file("examples/patients.xlsx")
    assert len(rows) == 5
    assert rows[0]["Patient Name"] == "John Doe"
