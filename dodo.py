
def task_wheel():
    """Build binary wheel."""
    return {
            'actions': ['python3.14 -m build -w'],
           }