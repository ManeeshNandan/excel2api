from excel2api.dependencies import dependency_order

def test_dependency_order():
    sheets = {
        "Patients": {"schema": "p", "references": [{"target_field":"doctor_id","source_sheet":"Doctors","source_key":"doctor_code","target_key":"doctor_code","source_value":"api_id"}]},
        "Doctors": {"schema": "d"},
    }
    assert dependency_order(sheets) == ["Doctors", "Patients"]

def test_dependency_cycle():
    sheets = {"A": {"schema":"a","references":[{"target_field":"x","source_sheet":"B","source_key":"x","target_key":"x","source_value":"id"}]}, "B": {"schema":"b","references":[{"target_field":"x","source_sheet":"A","source_key":"x","target_key":"x","source_value":"id"}]}}
    try:
        dependency_order(sheets)
        assert False
    except ValueError as exc:
        assert "Circular" in str(exc)
