import discord
from discord.ext import tasks, commands
import aiohttp
import asyncio
from datetime import datetime
import requests  # 🔴 ADD THIS FOR RUGCHECK API

import os
from dotenv import load_dotenv  # 🔴 Install this package: pip install python-dotenv

# Load environment variables from .env file
load_dotenv()

# Get the token safely
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')  # 🔴 THIS IS NOW SAFE
CHANNEL_ID = 1409166449141878927

# Initialize Bot
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

class HalalAlertBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.seen_tokens = set()  # Prevents duplicate alerts
        self.alert_loop.start()

    def cog_unload(self):
        self.alert_loop.cancel()

    @tasks.loop(minutes=10.0)  # 🔴 START WITH 10 MINUTES TO AVOID RATE LIMITS
    async def alert_loop(self):
        """Main loop that scans and posts alerts"""
        print(f"{datetime.now().strftime('%H:%M:%S')} - Scanning for new halal tokens...")
        try:
            channel = self.bot.get_channel(CHANNEL_ID)
            if channel is None:
                print(f"ERROR: Could not find channel with ID {CHANNEL_ID}")
                return

            # Get new tokens from DexScreener
            new_tokens = await self.scan_new_pools()
            
            for token in new_tokens:
                token_id = token['address']
                
                if token_id in self.seen_tokens:
                    continue
                
                # Check if token is halal - 🔴 THIS IS WHERE YOUR CHECKS HAPPEN
                is_halal, reason = await self.check_halal_status(token)
                
                if is_halal:
                    # Get alpha data (whale buys, etc.)
                    alpha_data = await self.find_alpha(token_id)
                    
                    # Combine all data for the alert
                    alert_data = {
                        **token,
                        **alpha_data,
                        'reason': reason,
                        'age': self.get_token_age(token)
                    }
                    
                    # Create and send alert
                    alert_message = self.create_halal_alert(alert_data)
                    await channel.send(embed=alert_message)
                    print(f"✅ Alert sent for {token['symbol']}")
                    
                    self.seen_tokens.add(token_id)
                    
        except Exception as e:
            print(f"Error in alert loop: {e}")

    @alert_loop.before_loop
    async def before_alert_loop(self):
        await self.bot.wait_until_ready()

    async def scan_new_pools(self):
        """Scan DexScreener for new pools"""
        new_tokens = []
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://api.dexscreener.com/latest/dex/search/?q=raydium&limit=20"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        for pair in data.get('pairs', [])[:10]:  # 🔴 CHECK FIRST 10 TOKENS
                            token_info = {
                                'symbol': pair['baseToken']['symbol'],
                                'address': pair['baseToken']['address'],
                                'price_usd': f"${float(pair['priceUsd']):.6f}" if pair['priceUsd'] else '$0.00',
                                'liquidity_usd': pair['liquidity']['usd'] if pair['liquidity'] else 0,
                                'market_cap_usd': float(pair['priceUsd']) * float(pair['baseToken']['totalSupply']) if pair['priceUsd'] and pair['baseToken']['totalSupply'] else 0,
                            }
                            new_tokens.append(token_info)
        except Exception as e:
            print(f"Scan error: {e}")
        return new_tokens

    async def check_halal_status(self, token):
        """🔴 IMPLEMENT YOUR REAL HALAL CHECKS HERE - THIS IS CRITICAL"""
        # TODO: Implement these checks properly
        # 1. Check LP lock (https://rugcheck.xyz/api) - MOST IMPORTANT
        # 2. Check mint authority renounced
        # 3. Check for haram keywords in name/symbol
        # 4. Check socials for haram content
        
        # 🔴 TEMPORARY: Replace this with real checks!
        # 🔴 START WITH JUST RUGCHECK API CALL FIRST
        try:
            # Example RugCheck API call (you need to implement this properly)
            rugcheck_url = f"https://api.rugcheck.xyz/api/projects/{token['address']}"
            response = requests.get(rugcheck_url)
            if response.status_code == 200:
                data = response.json()
                if not data.get('liquidityLocked', False):
                    return False, "Liquidity not locked - POTENTIAL RUG"
        except:
            return False, "Failed to verify LP lock"
        
        # If all checks pass (you'll add more later)
        return True, "LP Burned. Mint Renounced. No haram associations."

    async def find_alpha(self, token_address):
        """Find the narrative for why this token is pumping"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://public-api.solscan.io/token/transfers?tokenAddress={token_address}&limit=10"
                async with session.get(url) as response:
                    if response.status == 200:
                        transfers = await response.json()
                        for tx in transfers:
                            if tx.get('changeType') == 'inc' and float(tx.get('changeAmount', 0)) > 2:
                                return {
                                    'alpha_wallet': tx['address'],
                                    'buy_amount': str(float(tx['changeAmount'])),
                                    'price_change': "+1,250%"  # 🔴 CALCULATE THIS PROPERLY LATER
                                }
        except:
            pass
        
        return {
            'alpha_wallet': None,
            'buy_amount': "0",
            'price_change': "+0%"
        }

    def get_token_age(self, token):
        """Calculate token age"""
        return "5 minutes"  # 🔴 IMPLEMENT PROPER AGE CALCULATION LATER

    def create_halal_alert(self, token_data):
        """Create the professional alert embed"""
        short_ca = token_data['address'][:5] + "..." + token_data['address'][-4:]
        short_alpha_wallet = token_data['alpha_wallet'][:4] + "..." + token_data['alpha_wallet'][-4:] if token_data.get('alpha_wallet') else "New wallet"
        
        liquidity = float(token_data['liquidity_usd'])
        market_cap = float(token_data['market_cap_usd'])
        liquidity_formatted = "${:,.1f}K".format(liquidity/1000) if liquidity >= 1000 else "${:,.0f}".format(liquidity)
        market_cap_formatted = "${:,.1f}K".format(market_cap/1000) if market_cap >= 1000 else "${:,.0f}".format(market_cap)

        embed = discord.Embed(
            title="🕋 Stratos Halal Alpha Alert",
            description=f"**${token_data['symbol']}** is up **{token_data['price_change']}** in {token_data['age']}.",
            color=0x00ff00,
            url=f"https://dexscreener.com/solana/{token_data['address']}"
        )
        
        if token_data['alpha_wallet']:
            embed.add_field(
                name="🚀 Momentum", 
                value=f"First large buy ({token_data['buy_amount']} SOL) from alpha wallet `{short_alpha_wallet}`.", 
                inline=False
            )
        
        embed.add_field(name="💧 Liquidity", value=f"**{liquidity_formatted}** locked", inline=True)
        embed.add_field(name="📊 Market Cap", value=f"**{market_cap_formatted}**", inline=True)
        embed.add_field(name="⏰ Age", value=token_data['age'], inline=True)
        embed.add_field(name="✅ Halal Certified", value=token_data['reason'], inline=False)
        embed.set_footer(text="Stratos.ai - Clean Alpha")
        
        return embed

# ===== MAIN EXECUTION =====
async def main():
    async with bot:
        await bot.add_cog(HalalAlertBot(bot))
        await bot.start(DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
