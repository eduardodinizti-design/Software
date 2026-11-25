
ý/
lobby.protopk
base.protoactivity.proto"
GetLobbyGameBriefREQ"µ
LobbyGameBrief#
	game_kind (2.pk.CardGameKind*
game_sub_kind (2.pk.CardGameSubKind
blind (
minimum_buyin (
maximum_buyin (
player_amount ("9
GetLobbyGameBriefRSP!
games (2.pk.LobbyGameBrief"ò
LobbyGameDetail#
	game_kind (2.pk.CardGameKind*
game_sub_kind (2.pk.CardGameSubKind
room_id (

bb (

sb (
ante (
minimum_buyin (
maximum_buyin (

table_size	 (
player_amount
 ("
GetLobbyMttListREQ"Ò
LobbyMttGameDetail#
	game_kind (2.pk.CardGameKind*
game_sub_kind (2.pk.CardGameSubKind-

game_stage (2.pk.GameStage:
WAIT_STAGE

game_title (	
	game_icon (	
room_id (
buyin (
rebuyin (:0
	rebuy_num	 (:0
rebuy_multiple
 (:10$

rebuy_plan (2.pk.MttRebuyPlan
starting_chips (
game_create_time (
game_start_time (
ongoing_player_amount (
idle_player_amount (

table_size (
blind_up_time (:0
total_entries (
late_register_time (#
expected_late_register_time (
setting_start_time (
	unique_id (	
early_bird_level (:0
early_bird_multiple (:0
sort_no (
total_reward_chips (:0
total_reward_diamond (:0
total_reward_score (:0
	gtd_chips (:0 
simulator_restric (:false
is_new_user  (:false
playing! (:false
	is_signup" (:false
player_rebuy_num# (:0"P
GetLobbyMttListRSP
server_time (%
games (2.pk.LobbyMttGameDetail"†
JoinLobbyRoomREQ#
	game_kind (2.pk.CardGameKind*
game_sub_kind (2.pk.CardGameSubKind
blind (
room_id (:0"ž
JoinLobbyRoomRSP#
	game_kind (2.pk.CardGameKind*
game_sub_kind (2.pk.CardGameSubKind
blind (
room_id (
code (2.pk.ErrCode"w
ChooseLobbyGameREQ#
	game_kind (2.pk.CardGameKind*
game_sub_kind (2.pk.CardGameSubKind
blind (:0"Ñ
ChooseLobbyGameRSP#
	game_kind (2.pk.CardGameKind*
game_sub_kind (2.pk.CardGameSubKind
blind (
room_id (:0
minimum_buyin (
maximum_buyin (
code (2.pk.ErrCode"‰
ChangeLobbyRoomREQ#
	game_kind (2.pk.CardGameKind*
game_sub_kind (2.pk.CardGameSubKind
blind (
old_room_id ("§
ChangeLobbyRoomRSP#
	game_kind (2.pk.CardGameKind*
game_sub_kind (2.pk.CardGameSubKind
blind (
new_room_id (:0
code (2.pk.ErrCode"†
InviteFamilyFriendREQ
uid (
room_id (#
	game_kind (2.pk.CardGameKind*
game_sub_kind (2.pk.CardGameSubKind"¡
InviteFamilyFriendRSP
uid (
room_id (#
	game_kind (2.pk.CardGameKind*
game_sub_kind (2.pk.CardGameSubKind
code (2.pk.ErrCode"ˆ
BeInvitedFamilyGameBRC
name (	
room_id (#
	game_kind (2.pk.CardGameKind*
game_sub_kind (2.pk.CardGameSubKind"Í
FamilyGameDetail#
	game_kind (2.pk.CardGameKindE
game_sub_kind (2.pk.CardGameSubKind:CARD_GAME_SUB_KIND_NORMAL-

game_stage (2.pk.GameStage:
WAIT_STAGE
	unique_id (	
room_id (

bb (

sb (
ante (
straddle	 (:0
buyin
 (
game_create_time (
game_length (
remaining_game_seconds (
ongoing_player_amount (
idle_player_amount (

table_size (
ongoing (
gps_restric (:false

ip_restric (:false
vpip_restric (:false
vpip_limit_rate (:0
playing (+
tw_ofc_args (2.pk.TwOFCGameExtraArgsS
voluntary_straddle_type (2.pk.VoluntaryStraddleType:VOLUNTARY_STRADDLE_NONE"
GetFamilyGameListREQ";
GetFamilyGameListRSP#
games (2.pk.FamilyGameDetail"Ö
WaitingListDetail
union_id (
club_id (
	club_name (	
room_id (
seat_id (
	game_name (	#
	game_kind (2.pk.CardGameKind*
game_sub_kind (2.pk.CardGameSubKind0
game_currency_kind	 (2.pk.GameCurrencyKind

table_size
 (

bb (

sb (
ante (
remaining_seconds ("
GetWaitingListDetailREQ">
GetWaitingListDetailRSP#
info (2.pk.WaitingListDetail" 
DeclineSitREQ
room_id ("
LobbyNewDayBRC"
GetSysOpenInfoREQ"6
GetSysOpenInfoRSP!
detail (2.pk.SysOpenDetail"9
UpdateSysOpenInfoRSP!
detail (2.pk.SysOpenDetail"á
UserLevelInfo
uid (
exp (
level (
	max_level (#
daily_reward_received_level ("
daily_reward_received_date (%
monthly_reward_received_level ($
monthly_reward_received_date ("
GetLevelInfoREQ"2
GetLevelInfoRSP
info (2.pk.UserLevelInfo"
UnlockLevelREQ"L
UnlockLevelRSP
info (2.pk.UserLevelInfo
code (2.pk.ErrCode"
ReceiveLevelDailyRewardREQ"t
ReceiveLevelDailyRewardRSP
gold (
received_level (
received_date (
code (2.pk.ErrCode"
ReceiveLevelMonthlyRewardREQ"Ù
ReceiveLevelMonthlyRewardRSP<
rewards (2+.pk.ReceiveLevelMonthlyRewardRSP.RewardItem
received_level (
received_date (
code (2.pk.ErrCode1

RewardItem
item_id (

item_count ("W
LevelMonthlyTipsRSP
last_month_exp (
cur_month_exp (
	cur_level ("æ
PlayerLobbyInfoRSP
server_time (5
activity_config (2.pk.ActivityOpenConfigDetail*
sys_open_detail (2.pk.SysOpenDetail%

level_info (2.pk.UserLevelInfo*
fetched_family_guide_reward (:false
client_guide_status (%
fetched_first_recharge_reward (
fetched_init_reward ($
avatar_collect_reward_status	 ("
GetShootDragonDoorInfoREQ"F
GetShootDragonDoorInfoRSP
cards (
history_card_types ("–
ShootDragonDoorBetREQ/
bet (2".pk.ShootDragonDoorBetREQ.PlaceBetL
PlaceBet-
bet_type (2.pk.ShootDragonDoorCardType
	bet_value ("X
ShootDragonDoorBetRSP
card (
reward_diamond (
code (2.pk.ErrCode*b
ShootDragonDoorCardType
BET_MID
BET_BOTH_SIDE
BET_CARD
BET_LOW
BET_HIGH