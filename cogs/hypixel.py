import asyncio
from os import terminal_size
import re
from typing import Optional
from aiohttp.client_reqrep import ClientResponse
import discord

from discord.ext import commands
from discord.permissions import P

from utils.custom_context import MyContext
from utils.json_loader import read_json, write_json
from bot import MetroBot
from utils.useful import Cooldown, Embed

slayer_emojis = {
    'zombie' : '<:revs:917891728072130570>',
    'wolf' : '<:wolfs:917891802391019530>',
    'spider' : '<:spiders:917891764713578527>',
    'enderman' : '<:ender:917891833357565990>'
}
 
class View(discord.ui.View):
    def __init__(self, ctx : MyContext, data, profile, username, profile_str):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.data = data
        self.profile = profile
        self.username = username
        self.profile_str = profile_str

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.ctx.author.id:
            return True
        await interaction.response.send_message('This menu cannot be controlled by you, sorry!', ephemeral=True)
        return False

    @discord.ui.button(label='Request slayers', style=discord.ButtonStyle.gray, emoji='<:slayer:917893178953179186>')
    async def request_slayers(self, button : discord.ui.Button, interaction : discord.Interaction):

        slayer_data = self.data['profiles'][self.profile]['data']['slayers']
        to_append = []
        for x in slayer_data.keys():
            to_append.append(f"{slayer_emojis[x]} {x.capitalize()}: {slayer_data[x]['level']['currentLevel']}/{slayer_data[x]['level']['maxLevel']}")
        
        embed = Embed()
        embed.title = self.username
        embed.url = f"https://sky.shiiyu.moe/{self.username}/{self.profile_str}"
        embed.description = '\n'.join(to_append)
        embed.set_footer(text='This data is cached and can take up to 5 minutes to refresh.')
        await interaction.response.send_message(embed=embed, ephemeral=True)
            
    @discord.ui.button(label='Raw JSON Data', emoji='\U0001f4ce')
    async def raw_json_data(self, button : discord.ui.Button, interaction : discord.Interaction):
        if not self.ctx.author.id in self.ctx.bot.owner_ids:
            return await interaction.response.send_message('This feature is not for public use due to risk of being abused.', ephemeral=True)
        await interaction.response.defer()

        utility = self.ctx.bot.get_cog("utility")
        link = await utility.create_gist(str(self.data), filename='raw_data.py')

        embed = Embed()
        embed.title = 'Raw JSON Data'
        embed.description = str(link)

        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=False)

    @discord.ui.button(emoji='🗑️', style=discord.ButtonStyle.red)
    async def stop_pages(self, button: discord.ui.Button, interaction: discord.Interaction):
        """stops the pagination session."""
        await interaction.response.defer()
        await interaction.delete_original_message()
        self.stop()

        


def chunkIt(seq, num):
    avg = len(seq) / float(num)
    out = []
    last = 0.0

    while last < len(seq):
        out.append(seq[int(last):int(last + avg)])
        last += avg

    return out

info_file = read_json('info')
hypixel_api_key = info_file["hypixel_api_key"]

def setup(bot):
    bot.add_cog(hypixel(bot))

class hypixel(commands.Cog, description='Get stats from hypixel api'):
    
    def __init__(self, bot : MetroBot):
        self.bot = bot

        self.skills_cache = {}
        self.skill_emojis = {
            'taming' : '<:taming:917267753604350003>',
            'farming' : '<:farming:917267921330372649>',
            'mining' : '<:mining:917267986677645412>',
            'combat' : '<:combat:917268062904938566>',
            'foraging' : '<:forging:917268128973611019>',
            'fishing' : '<:fishing:917268183176609843>',
            'enchanting' : '<:enchanting:917268241188020285>',
            'alchemy' : '<:alchemy:917268296410226750>',
            'cata' : '<:cata:917268446943780956>'   
        }
        self.stat_emojis = {
            "health": '<:health:917580941956902942>',
            "defense": '<:defense:917581439648817163>',
            "strength": '<:strength:917581550516842586>',
            "speed": '<:speed:917581655785472060>',
            "crit_chance": '<:crit_chance:917581740057436182>',
            "crit_damage": '<:crit_damage:917581812442759168>',
            "intelligence": '<:intelligence:917581896010039336>',
            "sea_creature_chance": '<:sea_creature_chance:917581950389190707>',
            "magic_find": '<:magic_find:917582008128004186>' ,
            "pet_luck": '<:pet_luck:917582062683291748>',
            "ferocity": '<:ferocity:917582119927160853>',
            "ability_damage": '<:ability_damage:917582173702352926>',
            "mining_speed": '<:mining_speed:917582230245752843>',
            "mining_fortune": '<:mining_fortune:917582281865068624>',
            "farming_fortune": '<:farming_fortune:917582341541605386>',
            "foraging_fortune": '<:foraging_fortune:917582383270731817>',
            "pristine": '<:pristine:917582488073801738>',
            "true_defense": '<:true_defense:917582577815150603>',
            "attack_speed": '<:attack_speed:917582686560854097>'
        }
        self.mining_emojis = {
            "mithril" : '<:m_powder:917927029939245167>',
            "gemstone" : '<:g_powder:917927030216073256>',
            "tokens" : '<:token:917927030241247252>',
            "hotm" : "<:hotm:917924672069333013>"
        }

    @property
    def emoji(self) -> str:
        return '<:hypixel:912575998380355626>'

    async def handle_status_codes(self, s : ClientResponse):
        if s.status == 429:
            raise commands.BadArgument("The request limit for this command has been reached. Please try again later.")

        if s.status == 403:
            raise commands.BadArgument(f"Invaild API Key. Please contact {self.bot.owner}.")

        if s.status != 200:
            raise commands.BadArgument('Something went wrong please contact my owner.')

    async def uuid_from_username(self, username : str):
        
        async with self.bot.session.get(f"https://api.mojang.com/users/profiles/minecraft/{username}") as s:
            if s.status == 204:
                raise commands.BadArgument('That is not a vaild minecraft username!')
            elif s.status != 200:
                raise commands.BadArgument('Something went wrong please contact my owner.')

            res = await s.json()
            return res["id"]

    @commands.command(name='mc_uuid', aliases=['uuid'])
    @commands.check(Cooldown(2, 5, 3, 5, commands.cooldowns.BucketType.default))
    async def mc_uuid(self, ctx : MyContext, *, username : str):
        """Get the UUID and avatar of a minecraft username from Minecraft API"""

        uuid = await self.uuid_from_username(username)
        embed = Embed()
        embed.add_field(name=f'Username: {username}', value=f'**UUID:** `{uuid}`')
        embed.set_image(url=f'https://mc-heads.net/avatar/{uuid}')

        return await ctx.send(embed=embed)


    @commands.command(aliases=['bz'])
    @commands.check(Cooldown(2, 10, 2, 8, commands.BucketType.user))
    async def bazzar(self, ctx : MyContext, *, item : str):
        """
        Get item data of an item in the bazzar.
        This is powered by Hypixel API.

        You can find a full list of items here:
        https://gist.github.com/103f740138c9759c1fab06e0173e58eb
        Note at you may omit the capitalization and underscores
        """
        async with ctx.typing():
            async with self.bot.session.get(f"https://api.hypixel.net/skyblock/bazaar") as s:
                await self.handle_status_codes(s)

                res = await s.json()

                try:
                    item = res["products"][item.upper().replace(" ", "_")]
                except KeyError:
                    raise commands.BadArgument(f"Your item was not found!\nYou can get a full list of the items by typing `{ctx.prefix}help bz`")

                quick_sum = item["quick_status"]

                embed = Embed()
                embed.title = quick_sum["productId"]
                embed.add_field(
                    name='Sell Stats',
                    value=f'Sell Price: `{round(quick_sum["sellPrice"], 1):,}`'\
                        f'\nSell Volume: `{quick_sum["sellVolume"]:,}`'\
                        f'\nSell Orders: `{quick_sum["sellOrders"]}`'\
                        f'\nSell Moving Weekly: `{quick_sum["sellMovingWeek"]:,}`',
                    inline=False
                )
                embed.add_field(
                    name='Buy Stats',
                    value=f'Buy Price: `{round(quick_sum["buyPrice"], 1):,}`'\
                        f'\nBuy Volume: `{quick_sum["buyVolume"]:,}`'\
                        f'\nBuy Orders: `{quick_sum["buyOrders"]}`'\
                        f'\nBuy Moving Weekly: `{quick_sum["buyMovingWeek"]:,}`',
                    inline=False
                )
                embed.set_footer(text='Powered by Hypixel API.')
                return await ctx.send(embed=embed)


    @commands.command()
    @commands.check(Cooldown(2, 10, 2, 8, commands.BucketType.user))
    async def profiles(self, ctx : MyContext, *, username : str):
        """
        Get all the profiles of a username.
        Powered by Hypixel API.
        """

        async with ctx.typing():
            async with self.bot.session.get(f"https://api.hypixel.net/player?key=" + hypixel_api_key + "&name=" + username) as s:

                await self.handle_status_codes(s)

                res = await s.json()

                if res["player"] is None:
                    return await ctx.send("This user does not have any data in Hypixel API.")
                
                to_paginate = []
                for a, b in list(res['player']['stats']['SkyBlock']['profiles'].items()):
                    to_paginate.append(f"`{b['profile_id']}` - {b['cute_name']}")


                embed = Embed()
                embed.title = f'{res["player"]["displayname"]}\'s profiles'
                embed.description = '\n'.join(to_paginate)
                embed.set_footer(text='Powered by Hypixel API.')

                return await ctx.send(embed=embed)


    @commands.command(name='profile')
    @commands.check(Cooldown(4, 30, 6, 30, commands.BucketType.user))
    async def rewrite_profile(
        self, 
        ctx : MyContext, 
        username : str = commands.Option(description='Username to lookup'), 
        *,
        profile : Optional[str] = commands.Option(description='Profile to lookup')
        ):
        """
        View profile stats of a minecraft user.
        Powered by [SkyCrypt](https://sky.shiiyu.moe/api) and [Hypixel](https://api.hypixel.net/) API
        
        All bugs should be reported by joining my [`support server`](https://discord.gg/2ceTMZ9qJh)
        """
        profile_str = profile
        await ctx.defer(trigger_typing=False)
        if not ctx.interaction:
            await ctx.trigger_typing()

        async with self.bot.session.get(f"https://sky.shiiyu.moe/api/v2/coins/{username}") as v:
            res = await v.json()
            try:
                raise commands.BadArgument(res['error'])
            except KeyError:
                pass

            if not profile is None:
                for x in list(res['profiles'].items()):
                    if x[1]['cute_name'] == profile.capitalize():
                        profile = x[1]['profile_id']
                        break
                if profile == profile_str:
                    raise commands.BadArgument('Profile name was not found. Try running the command without the profile argument.')
                try:
                    bank = round(res['profiles'][profile]['bank'], 1)
                except KeyError:
                    bank = 0
                try:
                    purse = round(res['profiles'][profile]['purse'], 1)
                except KeyError:
                    purse = 0
                    
            else:
                coins = {}
                for x in list(res['profiles'].keys()):
                    try:
                        bank = round(res['profiles'][x]['bank'], 1)
                    except KeyError:
                        bank = 0
                    try:
                        purse = round(res['profiles'][x]['purse'], 1)
                    except KeyError:
                        purse = 0
                    coins[x] = purse + bank
            
                profile = max(coins)
    
        
        async with self.bot.session.get(f"https://sky.shiiyu.moe/api/v2/profile/{username}") as s:
            res = await s.json()
            try:
                raise commands.BadArgument(res['error'])
            except KeyError:
                pass
            try:
                souls = f"{res['profiles'][profile]['data']['fairy_souls']['collected']}/{res['profiles'][profile]['data']['fairy_souls']['total']}"
            except KeyError:
                souls = 0
            try:
                skill_av = res['profiles'][profile]['data']['average_level']
            except KeyError:
                skill_av = 0

            to_append, stats_to_append, fin = [], [], []

            for skill in list((res['profiles'][profile]['data']['levels']).keys()):
                if skill == 'carpentry':
                    break
                to_append.append(f"{self.skill_emojis[skill]} {skill.capitalize()}: {res['profiles'][profile]['data']['levels'][skill]['level']}")
            to_append.append(f"{self.skill_emojis['cata']} Catacombs: {res['profiles'][profile]['data']['dungeons']['catacombs']['level']['level']}")
            
            stats_to_pop = ['effective_health', 'damage', 'damage_increase', 'true_defense']
            stat_dict = res['profiles'][profile]['data']['stats']
            for x in stats_to_pop:
                try:
                    stat_dict.pop(x)
                except KeyError:
                    pass
            stat_dict['attack_speed'] = res['profiles'][profile]['data']['stats']['bonus_attack_speed']
            stat_dict.pop('bonus_attack_speed')

            for stat in list(stat_dict.keys()):
                stats_to_append.append(f"{self.stat_emojis[stat]} {stat.replace('_', ' ').capitalize()}: {res['profiles'][profile]['data']['stats'][stat]} \u2800\u2800")

            chunked = chunkIt(stats_to_append, 6)
            for x in chunked:
                fin.append(''.join(x))

            powder_data = f"{self.mining_emojis['hotm']} HotM Level: {res['profiles'][profile]['data']['mining']['core']['tier']['level']}/{res['profiles'][profile]['data']['mining']['core']['tier']['maxLevel']}"\
                        f"\n\nTotal Powder:"\
                        f"\n{self.mining_emojis['mithril']}: {res['profiles'][profile]['data']['mining']['core']['powder']['mithril']['total']:,}"\
                        f"\n{self.mining_emojis['gemstone']}: {res['profiles'][profile]['data']['mining']['core']['powder']['gemstone']['total']:,}"\
                        f"\n\nAvailable Powder:"\
                        f"\n{self.mining_emojis['mithril']}: {res['profiles'][profile]['data']['mining']['core']['powder']['mithril']['available']:,}"\
                        f"\n{self.mining_emojis['gemstone']}: {res['profiles'][profile]['data']['mining']['core']['powder']['gemstone']['available']:,}"

            embed = Embed()
            embed.title = username
            embed.url = f'https://sky.shiiyu.moe/{username.lower()}/{profile_str}'
            embed.description = f"<:fairy_soul:913249554097393665> **Fariy Souls:** {souls} \u2800\u2800\u2800\u2800\u2800\u2800 **Skill Average:** {round(skill_av, 1)}"
            embed.add_field(name='Purse', value=f'<:piggy_bank:913245005085286400> `{purse:,}`',inline=True)
            embed.add_field(name='Bank', value=f'<:gold:913245371650682920> `{bank:,}`')
            embed.add_field(name='Stats', value='\n'.join(fin), inline=False)
            embed.add_field(name='Skills', value='\n'.join(to_append), inline=False)
            
            embed.add_field(name='Heart of the Mountain', value=powder_data, inline=True)
            
            embed.set_footer(text='This data is cached and can take up to 5 minutes to refresh.')

        
        return await ctx.send(embed=embed, view=View(ctx, res, profile, username.lower(), profile_str))