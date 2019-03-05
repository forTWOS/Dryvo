from datetime import datetime, timedelta

import pytest

from server.api.blueprints import user
from server.api.database.models import Lesson, Student, User, WorkDay, Payment
from server.consts import DATE_FORMAT, WORKDAY_DATE_FORMAT


def test_work_days(teacher, auth, requester):
    date = datetime.utcnow() + timedelta(hours=10)
    first_kwargs_hour = 13
    kwargs = {
        "teacher": teacher,
        "day": 1,
        "from_hour": first_kwargs_hour,
        "from_minutes": 0,
        "to_hour": 17,
        "to_minutes": 0,
        "on_date": date,
    }
    day1 = WorkDay.create(**kwargs)
    kwargs.pop("on_date")
    kwargs["from_hour"] = 15
    day2 = WorkDay.create(**kwargs)
    print(WorkDay.query.all())
    auth.login(email=teacher.user.email)
    resp = requester.get("/teacher/work_days").json
    assert resp["data"][0]["from_hour"] == kwargs["from_hour"]
    day = date.date()
    resp = requester.get(f"/teacher/work_days?on_date=eq:{day}").json
    assert resp["data"][0]["from_hour"] == first_kwargs_hour


def test_add_work_day(teacher, auth, requester):
    auth.login(email=teacher.user.email)
    data = {
        "day": "tuesday",
        "from_hour": 13,
        "from_minutes": 0,
        "to_hour": 17,
        "to_minutes": 0,
        "on_date": "2018-11-27",
    }
    resp = requester.post("/teacher/work_days", json=data)
    assert "Day created" in resp.json["message"]
    assert resp.json["data"]
    assert resp.status_code == 201
    assert WorkDay.query.filter_by(from_hour=13).first().from_hour == data["from_hour"]


def test_add_work_day_invalid_values(teacher, auth, requester):
    auth.login(email=teacher.user.email)
    data = {
        "day": "tuesday",
        "from_hour": 20,
        "from_minutes": 0,
        "to_hour": 19,
        "to_minutes": 0,
        "on_date": "2018-11-27",
    }
    resp = requester.post("/teacher/work_days", json=data)
    assert "difference" in resp.json["message"]


def test_delete_work_day(teacher, auth, requester):
    auth.login(email=teacher.user.email)
    kwargs = {
        "teacher_id": 1,
        "day": 1,
        "from_hour": 13,
        "from_minutes": 0,
        "to_hour": 17,
        "to_minutes": 0,
    }
    day = WorkDay.create(**kwargs)
    resp = requester.delete(f"/teacher/work_days/{day.id}")
    assert "Day deleted" in resp.json["message"]
    resp = requester.delete("/teacher/work_days/8")
    assert "not exist" in resp.json["message"]


def test_available_hours_route(teacher, student, meetup, dropoff, auth, requester):
    auth.login(email=teacher.user.email)
    tomorrow = datetime.utcnow() + timedelta(days=1)
    date = tomorrow.strftime(WORKDAY_DATE_FORMAT)
    time_and_date = date + "T13:30:20.123123Z"
    data = {
        "day": "tuesday",
        "from_hour": 13,
        "from_minutes": 0,
        "to_hour": 17,
        "to_minutes": 0,
        "on_date": date,
    }
    requester.post("/teacher/work_days", json=data)  # we add a day
    # now let's add a lesson
    Lesson.create(
        teacher_id=teacher.id,
        student_id=student.id,
        creator_id=teacher.user.id,
        duration=40,
        date=datetime.strptime(time_and_date, DATE_FORMAT),
        meetup_place=meetup,
        dropoff_place=dropoff,
    )
    resp = requester.post(f"/teacher/{teacher.id}/available_hours", json={"date": date})
    assert len(resp.json["data"]) == 4
    assert "14:10" in resp.json["data"][0][0]
    resp = requester.post(
        f"/teacher/{teacher.id}/available_hours", json={"date": date, "duration": "100"}
    )
    assert len(resp.json["data"]) == 1


def test_teacher_available_hours(teacher, student, requester):
    tomorrow = datetime.utcnow() + timedelta(days=1)
    date = tomorrow.strftime(WORKDAY_DATE_FORMAT)
    time_and_date = date + "T13:30:20.123123Z"
    kwargs = {
        "teacher_id": teacher.id,
        "day": 1,
        "from_hour": tomorrow.hour,
        "from_minutes": tomorrow.minute,
        "to_hour": 23,
        "to_minutes": 59,
        "on_date": tomorrow,
    }
    WorkDay.create(**kwargs)
    assert next(teacher.available_hours(tomorrow))[0] == tomorrow


def test_add_payment(auth, requester, teacher, student):
    auth.login(email=teacher.user.email)
    resp = requester.post(
        "/teacher/add_payment", json={"amount": teacher.price, "student_id": student.id}
    )
    assert resp.json["data"]["amount"] == teacher.price


@pytest.mark.parametrize(
    ("amount, student_id, error"),
    ((None, 1, "Amount must be given."), (100, 10000, "Student does not exist.")),
)
def test_add_invalid_payment(auth, requester, teacher, amount, student_id, error):
    auth.login(email=teacher.user.email)
    resp = requester.post(
        "/teacher/add_payment", json={"amount": amount, "student_id": student_id}
    )
    assert resp.status_code == 400
    assert resp.json["message"] == error


def test_students(auth, teacher, requester):
    new_user = User.create(
        email="a@a.c", password="huh", name="absolutely", area="nope"
    )
    new_student = Student.create(teacher=teacher, creator=teacher.user, user=new_user)
    auth.login(email=teacher.user.email)
    resp = requester.get("/teacher/students?order_by=balance desc")
    assert resp.json["data"][1]["student_id"] == new_student.id
    resp = requester.get("/teacher/students?name=solut")
    assert resp.json["data"][0]["student_id"] == new_student.id
    resp = requester.get("/teacher/students?name=le:no way")
    assert not resp.json["data"]
    resp = requester.get("/teacher/students?limit=1")
    assert len(resp.json["data"]) == 1

