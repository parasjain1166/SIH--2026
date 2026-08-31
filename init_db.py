"""Initialize/reset RailBlock AI's SQLite database from the bundled prototype CSV data."""

from core.database import RailBlockDatabase
from core.kaggle_importer import KaggleDataImporter


def main():
    importer = KaggleDataImporter()
    stations = importer.load_real_stations()
    if not stations:
        raise SystemExit("No bundled station CSV data found; database was not changed.")
    sections = importer.build_track_sections_from_stations(stations)
    tasks = importer.load_real_maintenance_tasks()
    trains = importer.load_real_trains(sections)

    db = RailBlockDatabase()
    db.replace_dataset(stations, sections, tasks, trains, source_name="KAGGLE_REAL")
    print(f"SQLite database ready: {db.db_path}")
    for key, value in db.get_counts().items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
