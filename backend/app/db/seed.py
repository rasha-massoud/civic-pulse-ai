"""
Seed script — populates the CivicPulse AI database with realistic
Lebanese sample data (issues, reports, tasks) for local development
and dashboard demos.

Usage (from backend/, with your venv activated):
    python -m app.db.seed

Safe to re-run: it wipes existing rows in these tables first
(in FK-safe order) before inserting fresh seed data.
"""

from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import Issue, IssueStatus, Report, Task, User


def now_minus(days: int, hours: int = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days, hours=hours)


def run():
    db = SessionLocal()

    try:
        print("Clearing existing data (tasks, reports, issues, users)...")
        db.query(Task).delete()
        db.query(Report).delete()
        db.query(Issue).delete()
        db.query(User).delete()
        db.commit()

        # --- Admin user ---
        print(f"Creating admin user '{settings.ADMIN_USERNAME}'...")
        db.add(User(username=settings.ADMIN_USERNAME, hashed_password=hash_password(settings.ADMIN_PASSWORD)))

        # --- Issues ---
        print("Creating issues...")

        issue_hamra = Issue(
            category="Water Leak",
            severity="High",
            status=IssueStatus.OPEN,
            report_count=3,
            district="Hamra, Beirut",
            latitude=33.8959,
            longitude=35.4801,
            created_at=now_minus(9),
            updated_at=now_minus(1),
        )

        issue_achrafieh = Issue(
            category="Pothole",
            severity="Medium",
            status=IssueStatus.OPEN,
            report_count=1,
            district="Sassine Square, Achrafieh, Beirut",
            latitude=33.8886,
            longitude=35.5131,
            created_at=now_minus(4),
            updated_at=now_minus(4),
        )

        issue_bourj_hammoud = Issue(
            category="Garbage Overflow",
            severity="Medium",
            status=IssueStatus.IN_PROGRESS,
            report_count=2,
            district="Armenia Street, Bourj Hammoud",
            latitude=33.8823,
            longitude=35.5375,
            created_at=now_minus(10),
            updated_at=now_minus(2),
        )

        issue_jounieh = Issue(
            category="Broken Streetlight",
            severity="Low",
            status=IssueStatus.RESOLVED,
            report_count=1,
            district="Highway exit, Jounieh",
            latitude=33.9808,
            longitude=35.6178,
            created_at=now_minus(14),
            updated_at=now_minus(6),
        )

        issue_tripoli = Issue(
            category="Electrical Hazard",
            severity="Critical",
            status=IssueStatus.OPEN,
            report_count=2,
            district="Al Mina, Tripoli",
            latitude=34.4367,
            longitude=35.8308,
            created_at=now_minus(2),
            updated_at=now_minus(1),
        )

        issue_byblos = Issue(
            category="Damaged Sidewalk",
            severity="Low",
            status=IssueStatus.RESOLVED,
            report_count=1,
            district="Old Souks, Byblos (Jbeil)",
            latitude=34.1208,
            longitude=35.6481,
            created_at=now_minus(13),
            updated_at=now_minus(5),
        )

        db.add_all(
            [
                issue_hamra,
                issue_achrafieh,
                issue_bourj_hammoud,
                issue_jounieh,
                issue_tripoli,
                issue_byblos,
            ]
        )
        db.flush()  # so issue.id is available for FK assignment below

        # --- Reports ---
        print("Creating reports...")

        reports = [
            # Hamra water leak — 3 reports
            Report(
                issue_id=issue_hamra.id,
                phone_number="+9613123456",
                transcribed_text=(
                    "There's a water pipe burst near the Starbucks roundabout on "
                    "Hamra Street, it's been flooding the sidewalk for two days now."
                ),
                category="Water Leak",
                severity="High",
                latitude=33.8961,
                longitude=35.4803,
                language="en",
                created_at=now_minus(9),
            ),
            Report(
                issue_id=issue_hamra.id,
                phone_number="+9613234567",
                transcribed_text=(
                    "في تسرب مياه كبير عند دوار ستاربكس بشارع الحمرا، الشارع صار بركة."
                ),
                category="Water Leak",
                severity="High",
                latitude=33.8958,
                longitude=35.4800,
                language="ar",
                created_at=now_minus(7),
            ),
            Report(
                issue_id=issue_hamra.id,
                phone_number="+9613345678",
                transcribed_text=(
                    "Same water leak on Hamra St, cars are struggling to pass, "
                    "please send someone soon."
                ),
                category="Water Leak",
                severity="High",
                latitude=33.8960,
                longitude=35.4802,
                language="en",
                created_at=now_minus(1),
            ),
            # Achrafieh pothole — 1 report
            Report(
                issue_id=issue_achrafieh.id,
                phone_number="+9613456789",
                transcribed_text=(
                    "Big pothole right next to Sassine Square, almost damaged my "
                    "car's tire this morning."
                ),
                category="Pothole",
                severity="Medium",
                latitude=33.8886,
                longitude=35.5131,
                language="en",
                created_at=now_minus(4),
            ),
            # Bourj Hammoud garbage — 2 reports
            Report(
                issue_id=issue_bourj_hammoud.id,
                phone_number="+9613567890",
                transcribed_text=(
                    "Sukleen dumpsters overflowing on Armenia Street for over a "
                    "week now, the smell is unbearable."
                ),
                category="Garbage Overflow",
                severity="Medium",
                latitude=33.8823,
                longitude=35.5375,
                language="en",
                created_at=now_minus(10),
            ),
            Report(
                issue_id=issue_bourj_hammoud.id,
                phone_number="+9613678901",
                transcribed_text=(
                    "الزبالة تراكمت قدام بلدية برج حمود، في ذباب كتير وريحة ما بتتحمل."
                ),
                category="Garbage Overflow",
                severity="Medium",
                latitude=33.8825,
                longitude=35.5373,
                language="ar",
                created_at=now_minus(8),
            ),
            # Jounieh streetlight — 1 report
            Report(
                issue_id=issue_jounieh.id,
                phone_number="+9613789012",
                transcribed_text=(
                    "Streetlight near the Jounieh highway exit has been out for "
                    "weeks, it's very dark and unsafe at night."
                ),
                category="Broken Streetlight",
                severity="Low",
                latitude=33.9808,
                longitude=35.6178,
                language="en",
                created_at=now_minus(14),
            ),
            # Tripoli electrical hazard — 2 reports
            Report(
                issue_id=issue_tripoli.id,
                phone_number="+9616123456",
                transcribed_text=(
                    "Exposed electrical wires hanging low near a building entrance "
                    "in Al Mina, very dangerous, kids play nearby."
                ),
                category="Electrical Hazard",
                severity="Critical",
                latitude=34.4367,
                longitude=35.8308,
                language="en",
                created_at=now_minus(2),
            ),
            Report(
                issue_id=issue_tripoli.id,
                phone_number="+9616234567",
                transcribed_text=(
                    "في سلك كهربا مكشوف وقريب من مدخل بناية بالميناء، لازم حدا يجي بسرعة."
                ),
                category="Electrical Hazard",
                severity="Critical",
                latitude=34.4365,
                longitude=35.8310,
                language="ar",
                created_at=now_minus(1),
            ),
            # Byblos sidewalk — 1 report
            Report(
                issue_id=issue_byblos.id,
                phone_number="+9619123456",
                transcribed_text=(
                    "Sidewalk near the old souks in Byblos is cracked and uneven, "
                    "hard to walk with a stroller."
                ),
                category="Damaged Sidewalk",
                severity="Low",
                latitude=34.1208,
                longitude=35.6481,
                language="en",
                created_at=now_minus(13),
            ),
        ]
        db.add_all(reports)

        # --- Tasks (only for the in-progress issue) ---
        # assigned_to is a department string, not an individual field worker
        # (departments have no accounts/logins in this MVP — see Task model).
        print("Creating tasks...")

        task_bourj_hammoud = Task(
            issue_id=issue_bourj_hammoud.id,
            assigned_to="Waste Management Department",
            status="assigned",
            created_at=now_minus(2),
        )
        db.add(task_bourj_hammoud)

        db.commit()
        print("Seed complete: 6 issues, 10 reports, 1 task, 1 admin user.")
        print(f"Admin login: username='{settings.ADMIN_USERNAME}' password='{settings.ADMIN_PASSWORD}'")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()