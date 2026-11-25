
œ_

data.protopk
base.proto"ï
GetLastSevenDayStatsDataREQ

start_date (
end_date (#
game_filter (2.pk.GameFilter+
currency_filter (2.pk.CurrencyFilter"‚
CareerGameBrief
game_id (	
club_id (:0
	club_name (	
club_avatar (	
room_id (
host_uid (
	host_name (	
host_avatar (	
create_time	 (
utc
 (	#
	game_kind (2.pk.CardGameKind*
game_sub_kind (2.pk.CardGameSubKind0
game_currency_kind (2.pk.GameCurrencyKind
	game_name (	

sb (

bb (
ante (
buyin (
game_length (
start_chips (
up_blind_time (
itm (
enable_jackpot (

table_size (
straddle (
next_unique_id (	
next_ticket_price (:0
enable_insurance (:false
enable_evchop (:false
super_union_id (!
super_union_exchange_rate (5
bomb_pot_type  (2.pk.BombPotType:BOMB_POT_NONE
bomb_pot_min_ante! (:0
bomb_pot_max_ante" (:0
	rake_rate# (
rake_cap$ (:
voluntary_straddle_type% (2.pk.VoluntaryStraddleType
sevendeuce_reward& (/
squid_game_args' (2.pk.SquidGameExtraArgs/
sushi_game_args( (2.pk.SushiGameExtraArgs7
winstreak_game_args) (2.pk.WinStreakGameExtraArgs0
mataases_args* (2.pk.MataAsesGameExtraArgs,
badugi_args+ (2.pk.BadugiGameExtraArgs
player_winnings, (
jackpot_reward- (:0
hands_amount. (
player_buyin/ (
rank0 (:0
	ko_bounty1 (:0
insurance_profit2 (:0
evchop_profit3 (:0
color_game_bet4 (:0$
color_game_jackpot_reward5 (:0
mines_game_bet6 (:0$
mines_game_jackpot_reward7 (:0
squid_profit8 (:0
sushi_profit9 (:0
winstreak_profit: (:0

total_rake; (:0"π
GetLastSevenDayStatsDataRSP

start_date (
end_date (#
game_filter (2.pk.GameFilter+
currency_filter (2.pk.CurrencyFilter"
games (2.pk.CareerGameBrief"¢
GetGameStatsDetailREQ
game_id (	
club_id (
host_uid (0
game_currency_kind (2.pk.GameCurrencyKind#
	game_kind (2.pk.CardGameKind"™
GetGameStatsDetailRSP
game_id (	
club_id (2
hands (2#.pk.GetGameStatsDetailRSP.HandBriefD
players_profit (2,.pk.GetGameStatsDetailRSP.FamilyPlayerProfitÁ
	HandBrief
hand_id (	

hand_cards (
discard_card (
winnings (
hand_start_time (:0 
is_tongits_winner (:falseL
tongits_hand_status (2.pk.TongitsHandStatus:TONGITS_HAND_STATUS_NONE
hit_spin_hitpot (:false
tw_ofc_special_card	 (:0
	hand_rank
 (:0
	dark_card (:0
has_ot (:falseä
FamilyPlayerProfit
player (2.pk.PlayerInfo
	vip_level (2.pk.VIPLevel
winnings (
hands_count (
rake ("Õ
CollectHandBrief
hand_id (	#
	game_kind (2.pk.CardGameKind*
game_sub_kind (2.pk.CardGameSubKind0
game_currency_kind (2.pk.GameCurrencyKind
hand_start_time (
ante (:0
sb (:0
bb (:0
straddle	 (:0
club_id
 (
	club_name (	

hand_cards (
winnings (
super_union_id (:0
room_id (:0
tw_ofc_special_card (:0S
voluntary_straddle_type (2.pk.VoluntaryStraddleType:VOLUNTARY_STRADDLE_NONE!
super_union_exchange_rate (
discard_card (
	dark_card (
has_ot ("
GetCollectHandListREQ"<
GetCollectHandListRSP#
hands (2.pk.CollectHandBrief"V
CollectHandREQ
hand_id (	
club_id (
	club_name (	
room_id ("<
CollectHandRSP
hand_id (	
code (2.pk.ErrCode"#
UnCollectHandREQ
hand_id (	">
UnCollectHandRSP
hand_id (	
code (2.pk.ErrCode"#
GetHandDetailREQ
hand_id (	"ù#
GetHandDetailRSP
hand_id (	

start_time (
dealer_seat_id (#
	game_kind (2.pk.CardGameKind*
game_sub_kind (2.pk.CardGameSubKind
enable_anonymous (;
ofc_hand_detail (2".pk.GetHandDetailRSP.OFCHandDetail?
texas_hand_detail (2$.pk.GetHandDetailRSP.TexasHandDetailC
maubinh_hand_detail	 (2&.pk.GetHandDetailRSP.MauBinhHandDetail?
pusoy_hand_detail
 (2$.pk.GetHandDetailRSP.PusoyHandDetail@
tw_ofc_hand_detail (2$.pk.GetHandDetailRSP.TwOFCHandDetailE
mataases_hand_detail (2'.pk.GetHandDetailRSP.MataAsesHandDetailA
badugi_hand_detail (2%.pk.GetHandDetailRSP.BadugiHandDetailG
inbetween_hand_detail (2(.pk.GetHandDetailRSP.InBetweenHandDetailÓ	
TexasHandDetail
ante (

sb (

bb (
straddle (S
voluntary_straddle_type (2.pk.VoluntaryStraddleType:VOLUNTARY_STRADDLE_NONE
has_low_pot (C
rounds (23.pk.GetHandDetailRSP.TexasHandDetail.TexasRoundInfo/
multi_times_boards (2.pk.MultiTimesBoardE
players	 (24.pk.GetHandDetailRSP.TexasHandDetail.TexasHandPlayer&
	insurance
 (2.pk.InsuranceRecord 
evchop (2.pk.EvchopRecord
is_bomb_pot_hand (
bomb_pot_cur_ante (
is_sushi_game (
sushi_bonus (*

sushi_data (2.pk.SushiGameEventDataì
TexasHandPlayer
player (2.pk.PlayerInfo
vip_lv (2.pk.VIPLevel
seat_id (
begin_chips (
hi_pot_win_chips (
low_pot_win_chips ("
double_board_pot_win_chips (
hand1 (:0
hand2	 (:0
hand3
 (:0
hand4 (:0
hand5 (:0
hand6 (:0
discard_card (:0
	ko_bounty (
ko_bonus (
pos (,
player_stage (2.pk.PlayerCurrentStage
player_show_hand (
system_show_hand (
jackpot (
sevendeuce_profit (é
TexasRoundInfo$
round (2.pk.TexasBettingRound

board_card (
double_board_card ('
action_record (2.pk.ActionRecord∆
OFCHandDetail
blind (A
players (20.pk.GetHandDetailRSP.OFCHandDetail.OFCHandPlayer‚
OFCHandPlayer
player (2.pk.PlayerInfo)
vip_lv (2.pk.VIPLevel:VIP_LEVEL_0
seat_id (
begin_chips (
	win_chips (
top_card (
middle_card (
bottom_card (
	fold_card	 (Q

joker_info
 (2=.pk.GetHandDetailRSP.OFCHandDetail.OFCHandPlayer.OFCJokerInfo+
OFCJokerInfo
joker (
dest (á
MauBinhHandDetail
blind (I
players (28.pk.GetHandDetailRSP.MauBinhHandDetail.MauBinhHandPlayer.
maubinh_args (2.pk.MauBinhGameExtraArgsÁ
MauBinhHandPlayer
player (2.pk.PlayerInfo)
vip_lv (2.pk.VIPLevel:VIP_LEVEL_0
seat_id (
	win_chips (
	top_point (
middle_point (
bottom_point (
extra_point (
	ko_amount	 (
ko_point
 (
start_chips (
	end_chips (.
hand_detail (2.pk.MauBinhSeatHandDetail
jackpot (:0˘
PusoyHandDetail
blind (E
players (24.pk.GetHandDetailRSP.PusoyHandDetail.PusoyHandPlayer*

pusoy_args (2.pk.PusoyGameExtraArgs„
PusoyHandPlayer
player (2.pk.PlayerInfo)
vip_lv (2.pk.VIPLevel:VIP_LEVEL_0
seat_id (
	win_chips (
	top_point (
middle_point (
bottom_point (
extra_point (
	ko_amount	 (
ko_point
 (
start_chips (
	end_chips (,
hand_detail (2.pk.PusoySeatHandDetail
jackpot (:0Í
TwOFCHandDetail
blind (
tw_ofc_special_card (E
players (24.pk.GetHandDetailRSP.TwOFCHandDetail.TwOFCHandPlayer„
TwOFCHandPlayer
player (2.pk.PlayerInfo)
vip_lv (2.pk.VIPLevel:VIP_LEVEL_0
seat_id (
	win_chips (
	top_point (
middle_point (
bottom_point (
extra_point (
	ko_amount	 (
ko_point
 (
start_chips (
	end_chips (,
hand_detail (2.pk.TwOFCSeatHandDetail
jackpot (:0ê
MataAsesHandDetail
blind (
hi_ante (
lo_ante (
is_bomb_pot_hand (
bomb_pot_cur_ante (
has_ot (*
players (2.pk.MataAsesPlayerHistory"
round (2.pk.MataAsesRoundRD
boards	 (
	ot_boards
 (
	ot_dealer ({
BadugiHandDetail
ante (
blind ((
players (2.pk.BadugiPlayerHistory 
round (2.pk.BadugiRoundRDä
InBetweenHandDetail
blind (
	pot_chips (+
players (2.pk.InBetweenPlayerHistory$
round (2.pk.InBetweenActionRD"›
GameKindStatsData#
	game_kind (2.pk.CardGameKind
game_amount (:0
hands_amount (
player_winnings (*
game_sub_kind (2.pk.CardGameSubKind0
game_currency_kind (2.pk.GameCurrencyKind"D
GetLastThirtyDayStatsDataREQ

start_date (
end_date ("C
GetLastThirtyDayStatsDataRSP#
data (2.pk.GameKindStatsData"
GetTotalStatsDataREQ";
GetTotalStatsDataRSP#
data (2.pk.GameKindStatsData"Ÿ	
CareerStats
super_union_id (:0
union_id (:0
club_id (:0
uid (:0#
	game_kind (2.pk.CardGameKind*
game_sub_kind (2.pk.CardGameSubKind0
game_currency_kind (2.pk.GameCurrencyKind
vpip (:0
pfr	 (:0
	three_bet
 (:0
cbet (:0
check_raise (:0
fold_to_three_bet (:0
fold_to_cbet (:0
steal_blind (:0
wtsd (:0
wwsd (:0
roi (:0
fish_amount (:0
winner_amount (:0
rich_amount (:0
itm (:0
fantasy (:0
	refantasy (:0

aa_fantasy (:0

kk_fantasy (:0

qq_fantasy (:0
tripple_fantasy (:0
ofc_blood_war_hands (:0!
ofc_blood_in_out_hands (:0
ofc_joker_hands (:0
ofc_normal_hands  (:0
hands_amount! (:0
games_amount" (:0
maubinh_ko_amount# (:0"
maubinh_opponent_amount$ (:0%
maubinh_instant_win_amount% (:0%
maubinh_special_aces_hands& (:0
tw_ofc_ko_amount' (:0!
tw_ofc_opponent_amount( (:0$
tw_ofc_instant_win_amount) (:0
pusoy_ko_amount* (:0 
pusoy_opponent_amount+ (:0#
pusoy_instant_win_amount, (:0
af- (:0
total_profit. (:0"’
GetSelfCareerStatsREQ
super_union_id (
union_id (
club_id (#
	game_kind (2.pk.CardGameKind*
game_sub_kind (2.pk.CardGameSubKind0
game_currency_kind (2.pk.GameCurrencyKind"7
GetSelfCareerStatsRSP
stats (2.pk.CareerStats"Ø
GetTablePlayersCareerStatsREQ#
	game_kind (2.pk.CardGameKind9
players (2(.pk.GetTablePlayersCareerStatsREQ.Player*
game_sub_kind (2.pk.CardGameSubKind0
game_currency_kind (2.pk.GameCurrencyKindP
Player
super_union_id (
union_id (
club_id (
uid ("?
GetTablePlayersCareerStatsRSP
stats (2.pk.CareerStats"‰
GetPlayerCareerStatsREQ
super_union_id (
union_id (
club_id (
uid (#
	game_kind (2.pk.CardGameKind*
game_sub_kind (2.pk.CardGameSubKind0
game_currency_kind (2.pk.GameCurrencyKind"9
GetPlayerCareerStatsRSP
stats (2.pk.CareerStats"y
GetPlayerLobbyMttStatsREQ
uid (#
	game_kind (2.pk.CardGameKind*
game_sub_kind (2.pk.CardGameSubKind"Ä
GetPlayerLobbyMttStatsRSP
uid (
chips (:0
diamond (:0
score (:0
stats (2.pk.CareerStats"Ö
GetPlayerClubGameStatsREQ
club_id (

start_date (
end_date (
type (#
game_filter (2.pk.GameFilter"©
GetPlayerClubGameStatsRSP
club_id (

start_date (
end_date (
type (#
game_filter (2.pk.GameFilter"
games (2.pk.CareerGameBrief*_
CurrencyFilter
CURRENCY_FILTER_ALL
CURRENCY_FILTER_CLUB
CURRENCY_FILTER_FAMILY*È

GameFilter
GAME_FILTER_ALL
GAME_FILTER_NLH
GAME_FILTER_PLO
GAME_FILTER_OFC
GAME_FILTER_NLH_SNG
GAME_FILTER_PLO_SNG
GAME_FILTER_NLH_MTT
GAME_FILTER_PLO_MTT
GAME_FILTER_PLO_HILOW	
GAME_FILTER_MAUBINH

GAME_FILTER_PUSOY
GAME_FILTER_MAUBINH_MTT
GAME_FILTER_PUSOY_MTT
GAME_FILTER_AOF_NLH
GAME_FILTER_OTHER
GAME_FILTER_PLO_HILOW_SNG
GAME_FILTER_PLO_HILOW_MTT
GAME_FILTER_MIX_GAME
GAME_FILTER_TW_OFC
GAME_FILTER_OFC_MTT
GAME_FILTER_FLASH_NLH
GAME_FILTER_FLASH_PLO
GAME_FILTER_AOF_PLO
GAME_FILTER_MATAASES