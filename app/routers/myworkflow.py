# from fastapi import FastAPI, APIRouter
# from typing import Dict, Optional
# from datetime import datetime, timedelta
# from upstash_workflow.fastapi import Serve, AsyncWorkflowContext
# from app.services.email import send_booking_email_to_owner, send_booking_email_to_booker
# import logging

# # Import FastAPI app
# def import_app():
#     # from app.main import app
#     return app

# app = import_app()
# serve = Serve(app)  # Initialize Serve with FastAPI app
# router = APIRouter(prefix="/workflows", tags=["Automatic Workflows"])

# # Function to send an email (mocked for now)
# async def send_email(booking_owner_email,house_owner_email,house_owner_name,house_title,booking_owner_username,start_date, subject,end_date, body,booking_id,days_before:Optional[int]=1):
#     """
#     Simulates sending an email. Replace with actual email logic.
#     """
#     print(f"Sending email to {booking_owner_email} | Subject: {subject} | Body: {body}")
#     send_booking_email_to_booker(
#                     to_email=booking_owner_email,
#                     subject=f"Reminder: Your booking starts in {days_before} days",
#                     template_name="workflow_user.html",
#                     **{
#                         "house_title": house_title,
#                         "house_owner_name": house_owner_name,
#                         "booking_owner_username": booking_owner_username,
#                         "start_date": start_date,
#                         "end_date": end_date,
#                         "booking_id": booking_id
#                     }
#                 )
#     send_booking_email_to_owner(
#                     to_email=house_owner_email,
#                     subject=f"Reminder: A booking starts in {days_before} days",
#                     template_name="workflow_owner.html",
#                     **{
#                         "house_title": house_title,
#                         "house_owner_name": house_owner_name,
#                         "booking_owner_username": booking_owner_username,
#                         "start_date": start_date,
#                         "end_date": end_date,
#                         "booking_id": booking_id
#                     }
#                 )

# @serve.post("/api/py/reminder")
# async def booking_reminder(context: AsyncWorkflowContext[Dict[str, str]]) -> None:
#     """
#     Schedules email reminders before the booking start date.
#     """
#     request_data = context.request_payload

#     # Required Fields
#     booking_owner_email = request_data["email"]
#     booking_owner_username = request_data["username"]
#     house_title = request_data["house_title"]
#     rooms_no = request_data["rooms_no"]
#     start_date_str = request_data["start_date"]  # Expected format: YYYY-MM-DD HH:MM:SS
#     end_date_str = request_data["end_date"]  # Expected format: YYYY-MM-DD HH:MM:SS
#     booking_id=request_data["booking_id"]

#     # House Owner Details
#     house_owner_email = request_data["house_owner_email"]
#     house_owner_name = request_data["house_owner_name"]

#     # Convert string dates to datetime objects
#     start_date = datetime.strptime(start_date_str, "%Y-%m-%d %H:%M:%S")
#     end_date = datetime.strptime(end_date_str, "%Y-%m-%d %H:%M:%S")
    
#     # Reminder intervals (7, 5, 3, 1 days before start date)
#     reminder_days = [7, 5, 3, 1]
    
#     async def send_reminder(days_before: int):
#         """
#         Sends a reminder email.
#         """
#         subject = f"Reminder: Your Booking Starts in {days_before} Days"
#         body = f"Hello, your booking will start in {days_before} days on {start_date.strftime('%Y-%m-%d')}. Please be prepared."
#         await send_email(booking_owner_email,house_owner_email,house_owner_name,house_title,booking_owner_username,start_date, subject,end_date, body,booking_id,days_before)
#         print(f"Reminder sent: {days_before} days before booking.")

#     # Schedule reminders
#     for days in reminder_days:
#         reminder_time = (start_date - timedelta(days=days)).timestamp()
#         await context.sleep_until(f"reminder_{days}", reminder_time)
#         await context.run(f"send_reminder_{days}", lambda: send_reminder(days))

#     # Final reminder on the booking start date
#     async def final_reminder():
#         """
#         Sends a final email reminder on the booking date.
#         """
#         subject = "Reminder: Your Booking Starts Today!"
#         body = f"Hello, your booking starts today ({start_date.strftime('%Y-%m-%d')}). Enjoy your stay!"
#         await send_email(booking_owner_email,house_owner_email,house_owner_name,house_title,booking_owner_username,start_date, subject,end_date, body,booking_id,days_before=1)
#         print("Final reminder sent.")

#     await context.sleep_until("final_reminder", start_date.timestamp())
#     await context.run("send_final_reminder", final_reminder)
