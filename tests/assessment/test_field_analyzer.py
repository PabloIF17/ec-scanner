import pytest
from src.assessment.field_analyzer import FieldAnalyzer


def test_detects_email_fields():
    analyzer = FieldAnalyzer()
    result = analyzer.analyze("Contact", ["Id", "FirstName", "LastName", "Email", "Phone"])
    field_names = [f.field_name for f in result.sensitive_fields]
    assert "Email" in field_names
    assert "Phone" in field_names


def test_detects_custom_pii_fields():
    analyzer = FieldAnalyzer()
    result = analyzer.analyze("Account", ["Id", "Name", "Customer_SSN__c", "AnnualRevenue"])
    categories = [f.category for f in result.sensitive_fields]
    assert any("identity" in c for c in categories)
    assert any("financial" in c for c in categories)


def test_no_sensitive_fields():
    analyzer = FieldAnalyzer()
    result = analyzer.analyze("Site", ["Id", "Name", "Status", "CreatedDate"])
    assert not result.has_sensitive_fields


def test_highest_severity():
    analyzer = FieldAnalyzer()
    result = analyzer.analyze("Contact", ["Email", "Description"])
    assert result.highest_severity == "critical"
