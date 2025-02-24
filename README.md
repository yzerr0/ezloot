# EZLoot Bot - EST &gt;:)

## **Setup**

1. Install required packages - `pip install -r requirements.txt`
2. Run the app after connecting - `python bot.py`

## **Commands**

### User

1. **register**

   - Registers the user by initializing their gear slots

   - `!ezloot register`

2. **set**

   - Records an item for the specified gear slot for a registered user

   - `!ezloot set <slot> <item>`

     - `<slot>` - Gear slot (case-insensitive) which can be any from: **head - cloak - chest - gloves - legs - boots - necklace - belt - ring 1 - ring 2**
     - `<item>` - Item to record for specified spot - (***SPELLING AND PUNCTUATION MATTERS!!!!!!!!!!!!!!!****)*

3. **edit**

   - Allows a user to update an exiisting gear entry if slot is not locked

   - `!ezloot edit <slot> <new_item>`

     - `<slot>` - Specified gear slot

4. **showgear**

   - Displays user's current gear entries for all slots

   - `!ezloot showgear`

5. **showloot**

   - Displays loot records for specified user or user invoking the command if no parameter is provided
   - `!ezloot showloot [@User]`
     - `@User` (optional) - If provided shows loot for that user, otherwise shows command invoker

### Admin

1. **listusers**
   - Lists all registered users by finding their names
   - `!ezloot listusers`
2. **finditem**
   - Searches all users' gear slots for the specified item and returns a list of users who have that item in their record
   - `!ezloot finditem <item>`
     - `<item>` - Item name to search for (case-insensitive)
3. **assignloot**
   - Assigns loot for tthe specified gear slot to the mentioned user, locks that slot, and records the loot entry
   - `!ezloot assignloot @User <slot>`
     - `@User` - The user to receive the loot
     - `<slot>` - Gear slot of item
4. **viewloot**
   - Displays all loot entries the mentioned user has received
   - `!ezloot viewloot @User`
     - `@User` - Specific user to display loot from
5. **guildtotal**
   - Shows the total count of loot pieces awarded to all users combined
   - `!ezloot guildtotal`