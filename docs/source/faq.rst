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

You can check out `this article <https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID->`_ by discord's support on how to find User/Server/Message IDs.

Metro doesn't have slash commands showing up!
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In order to have application commands (slash commands) you need to invite the bot with the `applications.commands`` scope.

.. note:: 
     You do not need to kick and reinvite to bot to do this.

You can run `@Metro invite` and the links will have the scope already included. (or by `clicking here <https://discord.com/oauth2/authorize?client_id=788543184082698252&scope=bot+applications.commands&permissions=140932115831>`_)

.. image:: /images/applications_commands_faq_1.png

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




