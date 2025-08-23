from datetime import datetime, timezone

def get_time_delta_string(past_time: datetime, no_change_str):
    current_time = datetime.now(timezone.utc)
    time_difference = current_time - past_time

    days = time_difference.days
    hours, remainder = divmod(time_difference.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days:
        parts.append(f"{days} day{'s' if days > 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes > 1 else ''}")
    if seconds:
        parts.append(f"{seconds} second{'s' if seconds > 1 else ''}")
    
    if not parts:
        return no_change_str # For very small or no difference

    return ", ".join(parts) + " ago"
