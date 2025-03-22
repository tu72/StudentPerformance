from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Gets an item from a dictionary using key.
    """
    if not dictionary:
        return None
    return dictionary.get(key)

@register.filter
def filter_by_level(courses, level):
    """Filter courses by level"""
    return [course for course in courses if course.level == level]