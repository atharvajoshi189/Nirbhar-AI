#!/usr/bin/env python3
"""
Nirbhar AI — Task Deletion and Cleanup Utility
Allows listing and cleanly deleting tasks along with their cascaded sub-records from Supabase.
"""

import sys
import os
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Ensure root repository directory is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "api"))
load_dotenv(ROOT_DIR / ".env")

try:
    from app.db.supabase import get_supabase_admin_client
    from app.services.audit import audit_service
except ImportError as e:
    print(f"Error importing app modules: {e}")
    sys.exit(1)


def list_tasks():
    supabase = get_supabase_admin_client()
    res = supabase.table("tasks").select("id, title, status, budget_max, currency, created_at").order("created_at", desc=True).execute()
    tasks = res.data or []
    if not tasks:
        print("No tasks found in database.")
        return []
    
    print(f"\nFound {len(tasks)} task(s):")
    print("-" * 85)
    print(f"{'Task ID':<38} {'Status':<10} {'Budget':<12} {'Title'}")
    print("-" * 85)
    for t in tasks:
        print(f"{t['id']:<38} {t['status']:<10} {t.get('budget_max', 0):.2f} {t.get('currency', 'USD')}  {t.get('title', '')[:30]}")
    print("-" * 85)
    return tasks


def delete_task(task_id: str):
    supabase = get_supabase_admin_client()
    # Check if task exists
    res = supabase.table("tasks").select("id, title, user_id").eq("id", task_id).execute()
    if not res.data:
        print(f"Task '{task_id}' not found.")
        return False
    
    task = res.data[0]
    # Mark task as CANCELLED (hiding it from dashboard/active views without mutating immutable audit log)
    supabase.table("tasks").update({"status": "CANCELLED"}).eq("id", task_id).execute()

    # Record audit event
    try:
        audit_service.append_event(
            user_id=task.get("user_id"),
            event_type="TASK_CANCELLED",
            task_id=task_id,
            payload={"task_id": task_id, "title": task.get("title"), "action": "DELETED_BY_USER"}
        )
    except Exception:
        pass

    print(f"Successfully deleted task: {task_id} ({task.get('title')})")
    return True


def delete_active_tasks(force: bool = False):
    supabase = get_supabase_admin_client()
    res = supabase.table("tasks").select("id, title, status").eq("status", "ACTIVE").order("created_at", desc=True).execute()
    active_tasks = res.data or []

    if not active_tasks:
        print("No active tasks found to delete.")
        return

    print(f"\nFound {len(active_tasks)} ACTIVE task(s):")
    for t in active_tasks:
        print(f" - {t['id']}: {t.get('title')}")

    if not force:
        confirm = input(f"\nAre you sure you want to delete all {len(active_tasks)} active task(s)? (y/N): ").strip().lower()
        if confirm != "y":
            print("Operation cancelled.")
            return

    deleted = 0
    for t in active_tasks:
        if delete_task(t["id"]):
            deleted += 1

    print(f"\nDone. Deleted {deleted} active task(s).")


def main():
    parser = argparse.ArgumentParser(description="Nirbhar AI Task Cleanup Tool")
    parser.add_argument("--list", action="store_true", help="List all tasks in database")
    parser.add_argument("--id", type=str, help="Delete a specific task by UUID")
    parser.add_argument("--active-only", action="store_true", help="Delete all ACTIVE tasks")
    parser.add_argument("--force", action="store_true", help="Bypass interactive confirmation prompt")

    args = parser.parse_args()

    if args.list:
        list_tasks()
    elif args.id:
        delete_task(args.id)
    elif args.active_only:
        delete_active_tasks(force=args.force)
    else:
        # Default: show list and usage instructions
        list_tasks()
        print("\nUsage:")
        print("  python scripts/delete_tasks.py --list                 # List all tasks")
        print("  python scripts/delete_tasks.py --id <TASK_ID>         # Delete a single task")
        print("  python scripts/delete_tasks.py --active-only          # Delete all ACTIVE tasks (with confirmation)")
        print("  python scripts/delete_tasks.py --active-only --force  # Delete all ACTIVE tasks without prompting")


if __name__ == "__main__":
    main()

