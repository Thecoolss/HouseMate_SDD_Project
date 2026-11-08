from datetime import datetime


VALID_DIFFICULTIES = {"easy", "medium", "hard"}
VALID_BOOKING_RESOURCES = {"laundry", "kitchen", "living_room"}


def validate_title(title):
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Task title is required.")
    return title.strip()


def validate_difficulty(difficulty):
    if difficulty not in VALID_DIFFICULTIES:
        raise ValueError("Difficulty must be easy, medium, or hard.")


def validate_booking(resource, start_time, end_time):
    if not isinstance(resource, str) or not resource.strip():
        raise ValueError("Resource is required.")
    resource = resource.strip()
    if resource not in VALID_BOOKING_RESOURCES:
        raise ValueError("Choose a valid household resource.")
    if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
        raise ValueError("Booking start and end times are required.")
    if end_time <= start_time:
        raise ValueError("Booking end time must be after its start time.")
    return resource
