:orphan:

.. _faq:

Frequently Asked questions
============================

This is a list of Frequently Asked Questions regarding Metro.

.. contents:: Questions
    :local:

General
---------

Questions that are pointed toward some basic and general understanding.

How do I get the ID of something?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can check out `this article <https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID->`_ below by discord's support on how to find User/Server/Message IDs.

Metro doesn't have slash commands showing up!
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- In order to have application commands (slash commands) you need to invite the bot with the `applications.commands`` scope.

.. note:: 
     You do not need to kick and reinvite to bot to do this.

You can run `@Metro invite` and the links will have the scope already included. 

.. image:: /images/applications_commands_faq_1.png

- Have an admin of your server go to **Server Settings** > **Integrations** > **Metro** and set up the command permissions for your role.

- Head to the role permissions and make sure the roles have the `Use Application Commands`` permission. 

How can I change my prefix?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Things to note:

- Mentioning the bot will always work as a prefix. (@Metro)
- If you've invited the bot with `applications.commands` scope you can use slash commands by typing `/` and use Metro's commands

You can change your prefix by running `/prefix` or `@Metro prefix`

.. image:: /images/prefix_faq_1.png

Click `Add prefix` and enter your prefix into the prompt.

How do I change embed colors that Metro sends?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Metro's embed colors are decided by the top role color of the bot.

Change the bot's top role color to your desired color.


Giveaways
----------

Questions related to hosting giveaways with Metro.

How do I create a giveaway?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can use ``/giveaway make`` and respond to the questions.

Can you "rig" a giveaway's outcome?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

No. Giveaways are random, and there is no way to increase someone's chance to win.
Having higher roles, more bypass roles does not increase chances.

How can I reroll the outcome of a giveaway?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- You can use the ``Reroll Giveaway`` context menu on the giveaway message to reroll the winners.
  
- Using ``/giveaway reroll <ID>`` with the message ID of the giveaway

.. note::
    Check out `How do I get the ID of something?`_ if you need help getting the ID of the giveaway.

How can I give a role access to create giveaways?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can use ``/giveaway-settings manager <role>`` to whitelist a role.

All giveaway commands now need manager role to use.

- (``Manage Guild`` permissions will bypass this check)

If no manager is set, ``Manage Guild`` permissions are checked by default.

How can I add requirements to a giveaway?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can only use ``/giveaway start`` to add requirements at this time.

In the ``requirements`` argument you can use the ``role:`` flag.

.. image:: /images/requirements_faq_1.png

You can add more flags by splitting them with ``;;`` or ``|``

Additional Flags:

- **bypass:**
- **blacklist:**

Example of mixing multiple flags:

.. image:: /images/requirements_faq_2.png


  





