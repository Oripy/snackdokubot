This is a Discord bot to help Snackdoku posters to post in time. I can also help to write the post as it can gather info from puzzle links.

The following commands are to be sent in DM to manage the reminders and ask to retreive puzzle info:

**Scheduling**
> $schedule

will list the current planned schedule (ignoring past dates).

> $schedule    
> 2025-02-14 username http://sudokupad.app/somepuzzleid

will add/alter the reminder for 14th of February 2025. A message will be sent to _username_ on that date with the link and info.

> $schedule    
> 2025-02-14 delete

will remove the scheduled line for that date

several lines can be added/modified/deleted on the same message

**User defined reminder time preference**
> $time 14

will define the reminder time as being around 14:00 UTC for the user sending the command. Other users reminder time is not affected.

**Skipping reminder**
> $skip

will skip today's reminder.
This is useful when the post has already been posted and don't want the reminder to trigger anymore.

**Asking for puzzle info**
> $getinfo http://sudokupad.app/somepuzzleid

will send a message with formatted info on the puzzle (Title, Author, Rules) as well as a screenshot of the puzzle.
