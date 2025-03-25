# EZLoot Bot - EST &gt;:)

## **Setup**

1. **Install required packages** 

```bash
pip install -r requirements.txt
```

2. **Set environment variables**
   - `DISCORD_TOKEN`
   - `FIREBASE_CERTIFICATE`
   - `LOG_CHANNEL_ID` (optional, for interaction logs)
3. **Run the bot**

```python
python bot.py
```

## **Commands**

### User

1. **register**

   - Registers the user by initializing their gear slots

   - `!ezloot register`

2. **set**

   - Records an item for the specified gear slot for a registered user

   - `!ezloot set <slot> <item>`

     - `<slot>` - Gear slot (case-insensitive) which can be any from: **head - cloak - chest - gloves - legs - boots - necklace - bracelet- belt - ring 1 - ring 2 - weapon1 - weapon2 - arch1 - arch2**
     - `<item>` - Item to record for specified spot - (***SPELLING AND PUNCTUATION MATTERS!!!!!!!!!!!!!!!****)*

3. **edit**

   - Allows a user to update an exiisting gear entry if slot is not locked

   - `!ezloot edit <slot> <new_item>`

     - `<slot>` - Specified gear slot
     - `<new_item` - New item name

4. **pity**

   - Displays a user's current pity level
   - `!ezloot pity`
     - `[user_identifier]` - Admin only

5. **showgear**

   - Displays user's current gear entries for all slots

   - `!ezloot showgear`

     - `[user_identifier]` - Admin only

6. **showloot**

   - Displays user's loot records
   - `!ezloot showloot [@User]`
     - `[user_identifier]` - Admin only

7. **commands**

   - Displays a list of all available user commands
   - `!ezloot commands`

### Admin

 1. **listusers**
    - Lists all registered users by finding their names
    - `!ezloot listusers`
 2. **finditem**
    - Searches all users' gear slots for the specified item and returns a list of users who have that item in their record
    - `!ezloot finditem <item>`
      - `<item>` - Item name to search for (case-insensitive)
 3. **findbonusloot**
    - Searches all users' bonus loot entries that match the substring
    - `!ezloot findbonusloot <item>`
 4. **assignloot**
    - Assigns loot for tthe specified gear slot to the mentioned user, locks that slot, and records the loot entry
    - `!ezloot assignloot <user_identifier> <slot> [source]`
      - `<user_identifier>` - The user to receive the loot
      - `<slot>` - Gear slot of item
      - `[source]` - Optional string to append indicating where loot was obtained
 5. **assignbonusloot**
    - Assigns bonus loot for gear slot
    - `!ezloot assignbonusloot <user_identifier> <slot> <loot>`
 6. **addpity**
    - Increments a user's pity level by 1
    - `!ezloot addpity <user_identifier>`
 7. **setpity**
    - Sets the pity level for a user to a specified value
    - `!ezloot setpity <user_identifier> <pity_level>`
 8. **editgear**
    - Edits another user's gear slot directly even while locked
    - `!ezloot editgear <user_identifier> <slot> <new_item>`
 9. **unlock**
    - Unlocks a user's gear slot
    - `!ezloot unlock <user_identifier> <slot>`
10. **removegear**
    - Removes a specified user's entered gear item for a specified slot (unlocks as well)
    - `!ezloot removegear <user_identifier> <slot>`
11. **removeloot**
    - Removes a user's loot entry for a specified slot from their record
    - `!ezloot removeloot <user_identifier> <slot>`
12. **removebonusloot**
    - Removes a user's bonus loot entry for a specified slot
    - `!ezloot removebonusloot <user_identifier> <slot>`
13. **removeuser**
    - Removes a nonadmin user from the database
    - `!ezloot removeuser <user_identifier>`
14. **viewloot**
    - Displays all loot entries the mentioned user has received
    - `!ezloot viewloot <user_identifier>`
15. **guildtotal**
    - Shows the total count of loot pieces awarded to all users combined
    - `!ezloot guildtotal`
