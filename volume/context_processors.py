
from . import logic
from .models import Chart, Group, group_type_name


def nav_charts(request):
    return {
        "nav_charts": Chart.objects.all(),
    }


def nav_groups(request):
    nav_groups = {}
    for group_type in Group.GroupType:
        name = group_type_name(group_type)
        nav_groups[name] = {
            "title": group_type.label,
            "groups": [],
        }

    groups = Group.objects.all()
    for group in groups:
        name = group_type_name(group.group_type)

        nav_groups[name]["groups"].append(group)

    return {
        "nav_groups": nav_groups,
    }


def live_paused(request):
    return {
        "live_paused": logic.is_live_paused(),
    }
