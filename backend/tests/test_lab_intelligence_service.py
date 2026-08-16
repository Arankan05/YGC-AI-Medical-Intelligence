import uuid
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  - registers every table on Base.metadata
from app.db.database import Base
from app.models.lab_result import LabResult
from app.models.patient import Patient
from app.models.user import User
from app.services.lab_intelligence_service import (
    LabIntelligenceService,
    STATUS_HIGH,
    STATUS_LOW,
    STATUS_NORMAL,
    STATUS_UNKNOWN,
    TREND_DECREASING,
    TREND_INCREASING,
    TREND_INSUFFICIENT_DATA,
    TREND_STABLE,
)

TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def make_lab_result(
    value: str,
    reference_range: str | None = None,
    test_name: str = "Glucose",
    result_date: date | None = None,
    unit: str | None = "mg/dL",
):
    """Create a lightweight LabResult-like object for unit tests."""

    return SimpleNamespace(
        id=uuid4(),
        test_name=test_name,
        value=value,
        unit=unit,
        reference_range=reference_range,
        result_date=result_date,
        created_at=None,
        document_id=None,
        document=None,
    )


class TestLabIntelligenceService:
    def setup_method(self):
        self.service = LabIntelligenceService()

    def test_parse_numeric_value(self):
        assert self.service._parse_numeric_value("5.2") == 5.2
        assert self.service._parse_numeric_value("5.2 mg/dL") == 5.2
        assert self.service._parse_numeric_value("  5.2  ") == 5.2

    def test_parse_invalid_numeric_value_returns_none(self):
        assert self.service._parse_numeric_value("not available") is None
        assert self.service._parse_numeric_value("") is None
        assert self.service._parse_numeric_value(None) is None

    def test_censored_values_are_not_parsed_as_exact_numbers(self):
        """
        A laboratory reporting "<0.01" is stating the analyte fell below the
        assay's detection limit, not that it measured 0.01. Reading the digits
        alone would turn a non-result into a confident measurement.
        """
        assert self.service._parse_numeric_value("<0.01") is None
        assert self.service._parse_numeric_value("< 0.01") is None
        assert self.service._parse_numeric_value(">1000") is None
        assert self.service._parse_numeric_value("> 1000") is None
        assert self.service._parse_numeric_value("≤5") is None
        assert self.service._parse_numeric_value("≥5") is None

    def test_grouping_separator_values_are_not_parsed(self):
        """
        "1,200" is 1200 under en-US grouping and 1.2 under de-DE decimal
        notation. The old parser returned 1, understating the result 1200-fold.
        """
        assert self.service._parse_numeric_value("1,200") is None
        assert self.service._parse_numeric_value("1,200 mg/dL") is None

    def test_ambiguous_and_multi_number_values_are_not_parsed(self):
        assert self.service._parse_numeric_value("3.5 - 5.5") is None
        assert self.service._parse_numeric_value("Grade 2 at 5.2") is None
        assert self.service._parse_numeric_value("1e3") is None
        assert self.service._parse_numeric_value("~5") is None
        assert self.service._parse_numeric_value(".") is None

    def test_plain_values_with_units_still_parse(self):
        assert self.service._parse_numeric_value("5.2mg/dL") == 5.2
        assert self.service._parse_numeric_value("-1.5") == -1.5
        assert self.service._parse_numeric_value("0.5 %") == 0.5
        assert self.service._parse_numeric_value("5") == 5.0

    def test_censored_value_is_unknown_end_to_end(self):
        """The censored value must reach the caller as UNKNOWN, not as LOW."""
        result = make_lab_result(
            value="<0.01",
            reference_range="3.5 - 5.5",
        )

        analysis = self.service._analyze_result(result)

        assert analysis.numeric_value is None
        assert analysis.status == STATUS_UNKNOWN

    def test_parse_reference_range(self):
        assert self.service._parse_reference_range("3.5 - 5.5") == (
            3.5,
            5.5,
        )

        assert self.service._parse_reference_range("3.5–5.5") == (
            3.5,
            5.5,
        )

        assert self.service._parse_reference_range("3.5 to 5.5 mg/dL") == (
            3.5,
            5.5,
        )

    def test_invalid_reference_range_returns_none(self):
        assert self.service._parse_reference_range("unknown") is None
        assert self.service._parse_reference_range("") is None
        assert self.service._parse_reference_range(None) is None
        assert self.service._parse_reference_range("5.5 - 3.5") is None

    def test_malformed_reference_ranges_return_none(self):
        """
        A misread bound silently reclassifies every result measured against it,
        so an unparseable range must yield UNKNOWN rather than a guess.
        """
        assert self.service._parse_reference_range("1,200 - 1,500") is None
        assert self.service._parse_reference_range("< 5.5") is None
        assert self.service._parse_reference_range("> 40") is None
        assert self.service._parse_reference_range("Negative") is None
        assert self.service._parse_reference_range("-") is None

    def test_normal_value(self):
        result = make_lab_result(
            value="5.0",
            reference_range="3.5 - 5.5",
        )

        analysis = self.service._analyze_result(result)

        assert analysis.status == STATUS_NORMAL

    def test_boundary_values_are_normal(self):
        lower = make_lab_result(
            value="3.5",
            reference_range="3.5 - 5.5",
        )

        upper = make_lab_result(
            value="5.5",
            reference_range="3.5 - 5.5",
        )

        assert self.service._analyze_result(lower).status == STATUS_NORMAL
        assert self.service._analyze_result(upper).status == STATUS_NORMAL

    def test_high_value(self):
        result = make_lab_result(
            value="6.0",
            reference_range="3.5 - 5.5",
        )

        analysis = self.service._analyze_result(result)

        assert analysis.status == STATUS_HIGH

    def test_low_value(self):
        result = make_lab_result(
            value="3.0",
            reference_range="3.5 - 5.5",
        )

        analysis = self.service._analyze_result(result)

        assert analysis.status == STATUS_LOW

    def test_malformed_value_is_unknown(self):
        result = make_lab_result(
            value="not available",
            reference_range="3.5 - 5.5",
        )

        analysis = self.service._analyze_result(result)

        assert analysis.status == STATUS_UNKNOWN

    def test_missing_reference_range_is_unknown(self):
        result = make_lab_result(
            value="5.0",
            reference_range=None,
        )

        analysis = self.service._analyze_result(result)

        assert analysis.status == STATUS_UNKNOWN

    def test_malformed_reference_range_is_unknown(self):
        result = make_lab_result(
            value="5.0",
            reference_range="not available",
        )

        analysis = self.service._analyze_result(result)

        assert analysis.status == STATUS_UNKNOWN

    def test_trend_with_one_numeric_point_is_insufficient(self):
        point = self.service._trend_point(
            make_lab_result(
                value="5.0",
                reference_range="3.5 - 5.5",
                result_date=date(2026, 1, 1),
            )
        )

        trend = self.service._calculate_trend((point,))

        assert trend == TREND_INSUFFICIENT_DATA

    def test_increasing_trend(self):
        first = self.service._trend_point(
            make_lab_result(
                value="4.0",
                result_date=date(2026, 1, 1),
            )
        )

        second = self.service._trend_point(
            make_lab_result(
                value="6.0",
                result_date=date(2026, 2, 1),
            )
        )

        trend = self.service._calculate_trend((first, second))

        assert trend == TREND_INCREASING

    def test_decreasing_trend(self):
        first = self.service._trend_point(
            make_lab_result(
                value="6.0",
                result_date=date(2026, 1, 1),
            )
        )

        second = self.service._trend_point(
            make_lab_result(
                value="4.0",
                result_date=date(2026, 2, 1),
            )
        )

        trend = self.service._calculate_trend((first, second))

        assert trend == TREND_DECREASING

    def test_stable_trend(self):
        first = self.service._trend_point(
            make_lab_result(
                value="5.0",
                result_date=date(2026, 1, 1),
            )
        )

        second = self.service._trend_point(
            make_lab_result(
                value="5.1",
                result_date=date(2026, 2, 1),
            )
        )

        trend = self.service._calculate_trend((first, second))

        assert trend == TREND_STABLE

    def test_invalid_points_are_ignored_for_trend_direction(self):
        valid_first = self.service._trend_point(
            make_lab_result(
                value="4.0",
                result_date=date(2026, 1, 1),
            )
        )

        invalid = self.service._trend_point(
            make_lab_result(
                value="unknown",
                result_date=date(2026, 2, 1),
            )
        )

        valid_last = self.service._trend_point(
            make_lab_result(
                value="6.0",
                result_date=date(2026, 3, 1),
            )
        )

        trend = self.service._calculate_trend(
            (valid_first, invalid, valid_last)
        )

        assert trend == TREND_INCREASING


# ----------------------------------------------------------------------
# Database-backed tests for the public service methods.
#
# These follow the SQLite/StaticPool style of test_medication_safety_api.py
# rather than mocking the Session: the public methods are mostly query
# construction, so patient scoping and ORDER BY semantics are only meaningful
# if the SQL actually executes.
# ----------------------------------------------------------------------


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=test_engine)
    session = TestSessionLocal()
    yield session
    session.rollback()
    session.close()
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def patient_a(db_session):
    return _create_patient(db_session, "patient_a@example.com")


@pytest.fixture
def patient_b(db_session):
    return _create_patient(db_session, "patient_b@example.com")


@pytest.fixture
def service():
    return LabIntelligenceService()


def _create_patient(db, email):
    user = User(id=uuid.uuid4(), email=email)
    db.add(user)
    db.commit()
    patient = Patient(id=uuid.uuid4(), user_id=user.id)
    db.add(patient)
    db.commit()
    return patient


def _add_lab_result(
    db,
    patient,
    test_name="Glucose",
    value="5.0",
    unit="mg/dL",
    reference_range="3.5 - 5.5",
    result_date=None,
):
    lab_result = LabResult(
        id=uuid.uuid4(),
        patient_id=patient.id,
        test_name=test_name,
        value=value,
        unit=unit,
        reference_range=reference_range,
        result_date=result_date,
    )
    db.add(lab_result)
    db.commit()
    return lab_result


class TestAnalyzePatientLabs:
    def test_returns_analyses_for_the_patient(self, service, db_session, patient_a):
        _add_lab_result(db_session, patient_a, value="5.0", result_date=date(2026, 1, 1))

        analyses = service.analyze_patient_labs(
            db=db_session,
            patient_id=patient_a.id,
        )

        assert len(analyses) == 1
        assert analyses[0].test_name == "Glucose"
        assert analyses[0].numeric_value == 5.0
        assert analyses[0].status == STATUS_NORMAL

    def test_patient_with_no_results_returns_empty(self, service, db_session, patient_a):
        analyses = service.analyze_patient_labs(
            db=db_session,
            patient_id=patient_a.id,
        )

        assert analyses == ()

    def test_statuses_are_classified_from_the_reference_range(
        self, service, db_session, patient_a
    ):
        _add_lab_result(db_session, patient_a, test_name="Low", value="3.0")
        _add_lab_result(db_session, patient_a, test_name="Normal", value="5.0")
        _add_lab_result(db_session, patient_a, test_name="High", value="6.0")
        _add_lab_result(db_session, patient_a, test_name="Unparseable", value="n/a")
        _add_lab_result(
            db_session,
            patient_a,
            test_name="NoRange",
            value="5.0",
            reference_range=None,
        )

        analyses = service.analyze_patient_labs(
            db=db_session,
            patient_id=patient_a.id,
        )
        by_name = {a.test_name: a.status for a in analyses}

        assert by_name["Low"] == STATUS_LOW
        assert by_name["Normal"] == STATUS_NORMAL
        assert by_name["High"] == STATUS_HIGH
        assert by_name["Unparseable"] == STATUS_UNKNOWN
        assert by_name["NoRange"] == STATUS_UNKNOWN

    def test_dated_results_are_newest_first_and_undated_results_come_last(
        self, service, db_session, patient_a
    ):
        _add_lab_result(db_session, patient_a, test_name="Undated", result_date=None)
        _add_lab_result(
            db_session, patient_a, test_name="Older", result_date=date(2026, 1, 1)
        )
        _add_lab_result(
            db_session, patient_a, test_name="Newer", result_date=date(2026, 6, 1)
        )

        analyses = service.analyze_patient_labs(
            db=db_session,
            patient_id=patient_a.id,
        )

        assert [a.test_name for a in analyses] == ["Newer", "Older", "Undated"]


class TestGetAvailableTests:
    def test_returns_distinct_names_sorted(self, service, db_session, patient_a):
        _add_lab_result(db_session, patient_a, test_name="Sodium")
        _add_lab_result(db_session, patient_a, test_name="Glucose")
        _add_lab_result(db_session, patient_a, test_name="Glucose")

        names = service.get_available_tests(
            db=db_session,
            patient_id=patient_a.id,
        )

        assert names == ("Glucose", "Sodium")

    def test_names_are_deduplicated_case_insensitively(
        self, service, db_session, patient_a
    ):
        _add_lab_result(db_session, patient_a, test_name="Glucose")
        _add_lab_result(db_session, patient_a, test_name="glucose")
        _add_lab_result(db_session, patient_a, test_name="  GLUCOSE  ")

        names = service.get_available_tests(
            db=db_session,
            patient_id=patient_a.id,
        )

        assert len(names) == 1

    def test_patient_with_no_results_returns_empty(self, service, db_session, patient_a):
        assert (
            service.get_available_tests(db=db_session, patient_id=patient_a.id) == ()
        )


class TestGetTestTrend:
    def test_points_are_ordered_oldest_to_newest(self, service, db_session, patient_a):
        _add_lab_result(
            db_session, patient_a, value="6.0", result_date=date(2026, 3, 1)
        )
        _add_lab_result(
            db_session, patient_a, value="4.0", result_date=date(2026, 1, 1)
        )

        trend = service.get_test_trend(
            db=db_session,
            patient_id=patient_a.id,
            test_name="Glucose",
        )

        assert [p.numeric_value for p in trend.points] == [4.0, 6.0]
        assert trend.trend == TREND_INCREASING

    def test_matching_is_case_insensitive_and_trims_whitespace(
        self, service, db_session, patient_a
    ):
        _add_lab_result(db_session, patient_a, test_name="Glucose")

        trend = service.get_test_trend(
            db=db_session,
            patient_id=patient_a.id,
            test_name="  gLuCoSe  ",
        )

        assert len(trend.points) == 1

    def test_decreasing_and_stable_directions(self, service, db_session, patient_a):
        _add_lab_result(
            db_session, patient_a, test_name="Down", value="6.0",
            result_date=date(2026, 1, 1),
        )
        _add_lab_result(
            db_session, patient_a, test_name="Down", value="4.0",
            result_date=date(2026, 2, 1),
        )
        _add_lab_result(
            db_session, patient_a, test_name="Flat", value="5.0",
            result_date=date(2026, 1, 1),
        )
        _add_lab_result(
            db_session, patient_a, test_name="Flat", value="5.1",
            result_date=date(2026, 2, 1),
        )

        down = service.get_test_trend(
            db=db_session, patient_id=patient_a.id, test_name="Down"
        )
        flat = service.get_test_trend(
            db=db_session, patient_id=patient_a.id, test_name="Flat"
        )

        assert down.trend == TREND_DECREASING
        assert flat.trend == TREND_STABLE

    def test_single_result_is_insufficient_data(self, service, db_session, patient_a):
        _add_lab_result(db_session, patient_a, result_date=date(2026, 1, 1))

        trend = service.get_test_trend(
            db=db_session,
            patient_id=patient_a.id,
            test_name="Glucose",
        )

        assert trend.trend == TREND_INSUFFICIENT_DATA
        assert len(trend.points) == 1

    def test_unknown_test_returns_no_points(self, service, db_session, patient_a):
        _add_lab_result(db_session, patient_a, test_name="Glucose")

        trend = service.get_test_trend(
            db=db_session,
            patient_id=patient_a.id,
            test_name="Sodium",
        )

        assert trend.points == ()
        assert trend.trend == TREND_INSUFFICIENT_DATA

    def test_blank_test_name_returns_no_points(self, service, db_session, patient_a):
        _add_lab_result(db_session, patient_a, test_name="Glucose")

        trend = service.get_test_trend(
            db=db_session,
            patient_id=patient_a.id,
            test_name="   ",
        )

        assert trend.points == ()


class TestGetAllTestTrends:
    def test_returns_one_trend_per_available_test(
        self, service, db_session, patient_a
    ):
        _add_lab_result(
            db_session, patient_a, test_name="Sodium", result_date=date(2026, 1, 1)
        )
        _add_lab_result(
            db_session, patient_a, test_name="Glucose", value="4.0",
            result_date=date(2026, 1, 1),
        )
        _add_lab_result(
            db_session, patient_a, test_name="Glucose", value="6.0",
            result_date=date(2026, 2, 1),
        )

        trends = service.get_all_test_trends(
            db=db_session,
            patient_id=patient_a.id,
        )

        assert [t.test_name for t in trends] == ["Glucose", "Sodium"]
        assert trends[0].trend == TREND_INCREASING
        assert trends[1].trend == TREND_INSUFFICIENT_DATA

    def test_patient_with_no_results_returns_empty(self, service, db_session, patient_a):
        assert (
            service.get_all_test_trends(db=db_session, patient_id=patient_a.id) == ()
        )


class TestPatientIsolation:
    """
    Security tests: every public method filters on patient_id, so one patient's
    laboratory data can never surface under another patient's identifier.
    """

    def test_analyze_patient_labs_excludes_other_patients(
        self, service, db_session, patient_a, patient_b
    ):
        _add_lab_result(db_session, patient_a, test_name="A-Glucose")
        _add_lab_result(db_session, patient_b, test_name="B-Sodium")

        analyses = service.analyze_patient_labs(
            db=db_session,
            patient_id=patient_a.id,
        )

        assert [a.test_name for a in analyses] == ["A-Glucose"]

    def test_get_available_tests_excludes_other_patients(
        self, service, db_session, patient_a, patient_b
    ):
        _add_lab_result(db_session, patient_a, test_name="A-Glucose")
        _add_lab_result(db_session, patient_b, test_name="B-Sodium")

        assert service.get_available_tests(
            db=db_session, patient_id=patient_a.id
        ) == ("A-Glucose",)

    def test_get_test_trend_does_not_match_another_patients_test(
        self, service, db_session, patient_a, patient_b
    ):
        """A shared test name must not leak patient B's values to patient A."""
        _add_lab_result(
            db_session, patient_b, test_name="Glucose", value="6.0",
            result_date=date(2026, 1, 1),
        )
        _add_lab_result(
            db_session, patient_b, test_name="Glucose", value="9.0",
            result_date=date(2026, 2, 1),
        )

        trend = service.get_test_trend(
            db=db_session,
            patient_id=patient_a.id,
            test_name="Glucose",
        )

        assert trend.points == ()

    def test_get_all_test_trends_excludes_other_patients(
        self, service, db_session, patient_a, patient_b
    ):
        _add_lab_result(db_session, patient_a, test_name="A-Glucose")
        _add_lab_result(db_session, patient_b, test_name="B-Sodium")

        trends = service.get_all_test_trends(
            db=db_session,
            patient_id=patient_a.id,
        )

        assert [t.test_name for t in trends] == ["A-Glucose"]