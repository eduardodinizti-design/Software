
¾A
activity.protopk
base.proto")
SyncRedEnvelopeNumBRC
last_num ("
GetRedEnvelopeActivityTimeREQ"k
GetRedEnvelopeActivityTimeRSP
left_task_seconds (
left_activity_seconds (
last_num ("l
RedEnvelopeRecordInfo
uid (
name (	%
type (2.pk.RedEnvelopeItemType
	timestamp ("
DrawRedEnvelopeREQ"X
DrawRedEnvelopeRSP
code (2.pk.ErrCode'
info (2.pk.RedEnvelopeRecordInfo"
GetSelfRedEnvelopeInfoREQ"ð
GetSelfRedEnvelopeInfoRSP
last_num (
used_num (
from_hands_num (
from_new_room_num (
curr_hands_num (
left_task_seconds (
left_activity_seconds (*
records (2.pk.RedEnvelopeRecordInfo"'

RewardItem

id (
count ("K
TreasureReward
gold (
xcoin (
item (2.pk.RewardItem"S
TreasureHistoryLog
uid (
name (	"
reward (2.pk.TreasureReward"
GetTreasureInfoREQ"„
GetTreasureInfoRSP
	gold_data (

xcoin_data (!
	item_data (2.pk.RewardItem$
logs (2.pk.TreasureHistoryLog"
DrawTreasureREQ

os (	"T
DrawTreasureRSP
code (2.pk.ErrCode&
record (2.pk.TreasureHistoryLog"
GetTimingRewardStatusREQ"ì
GetTimingRewardStatusRSP
diamond_amount (:0
diamond_per_round_time (#
diamond_cur_round_left_time (
gold_amount (:0
gold_per_round_time ( 
gold_cur_round_left_time (
code (2.pk.ErrCode":
FetchTimingRewardREQ"
type (2.pk.TimingRewardType"h
FetchTimingRewardRSP"
type (2.pk.TimingRewardType
amount (:0
code (2.pk.ErrCode"
FetchDailyShareRewardREQ"b
FetchDailyShareRewardRSP
diamond_amount (
gold_amount (
code (2.pk.ErrCode"
FetchNewUserNDayRewardREQ"Ÿ
FetchNewUserNDayRewardRSP
diamond_amount (
gold_amount (:
vip_card_type (2.pk.VIPCardType:VIP_CARD_TYPE_NONE
code (2.pk.ErrCode"
GetDailyLoginRewardStatusREQ"
DailyLoginRewardConfig
diamond_amount (
gold_amount (:
vip_card_type (2.pk.VIPCardType:VIP_CARD_TYPE_NONE"
GetDailyLoginRewardStatusRSP*
config (2.pk.DailyLoginRewardConfig
reward_day_index (:0
next_left_seconds (
code (2.pk.ErrCode"-
FetchDailyLoginRewardREQ
	day_index ("±
FetchDailyLoginRewardRSP
	day_index (
diamond_amount (
gold_amount (:
vip_card_type (2.pk.VIPCardType:VIP_CARD_TYPE_NONE
code (2.pk.ErrCode"
GetGoldSponsorStatusREQ"B
GetGoldSponsorStatusRSP
gold_amount (

left_times ("
FetchGoldSponsorRewardREQ"e
FetchGoldSponsorRewardRSP
code (2.pk.ErrCode
gold_amount (:0

left_times (:0"J
BindReferrerCodeREQ
referrer_uid (
	device_id (	

os (	"F
BindReferrerCodeRSP
referrer_uid (
code (2.pk.ErrCode"
GetReferrerNumREQ",
GetReferrerNumRSP
referrer_num (:0"A
RebateReward!

money_kind (2.pk.MoneyKind
amount ("W
SyncRebateHandsCountBRC
family_hands_count ( 
reward (2.pk.RebateReward"t
RedDotNoticeRSP,
type (2.pk.RedDotNoticeRSP.RedDotType"3

RedDotType%
!RED_DOT_TYPE_ACCUMULATED_RECHARGE"œ
ActivityOpenConfigDetail
id (2.pk.ActivityID
version (
activity_start_time (
activity_end_time (
activity_close_time ("
GetActivityOpenConfigREQ"f
GetActivityOpenConfigRSP
server_time (5
activity_config (2.pk.ActivityOpenConfigDetail"
GetAccumulatedRechargeInfoREQ"N
GetAccumulatedRechargeInfoRSP
recharge_diamond (
fetched_ids (")
FetchAccumulatedRechargeREQ

id ("D
FetchAccumulatedRechargeRSP

id (
code (2.pk.ErrCode"
FetchInitRewardREQ"•
FetchInitRewardRSP
code (2.pk.ErrCode
gold_amount (:0
score_amount (:0
next_gold_amount (
next_score_amount ("
FetchFamilyGuideRewardREQ"G
FetchFamilyGuideRewardRSP
diamond (
code (2.pk.ErrCode"E
FirstRechargeRewardBRC
reward_diamond (
reward_gold ("0
FetchAvatarCollectRewardREQ
	series_id ("K
FetchAvatarCollectRewardRSP
	series_id (
code (2.pk.ErrCode"
GetRevengeGiftBagInfoREQ"ß
GetRevengeGiftBagInfoRSPA
bag_info (2/.pk.GetRevengeGiftBagInfoRSP.RevengeGiftBagInfo
remain_time (
pop_windows (V
RevengeGiftBagInfo
price (

price_list (
diamond (
gold (")
ReceivedRevengeGiftBagRSP
gold ("›
MonopolyPlayerInfo
total_score (
position (

free_count (
roll_multiple (
player_guide (
allow_change_multiple ("a
MonopolyRankPlayerBrief
uid (
name (	
avatar (	
score (
rank ("œ
MonopolyRankData3
self_rank_data (2.pk.MonopolyRankPlayerBrief,
players (2.pk.MonopolyRankPlayerBrief
round (
round_end_time ("
GetMonopolyInfoREQ"h
GetMonopolyInfoRSP)
	self_info (2.pk.MonopolyPlayerInfo'
	rank_data (2.pk.MonopolyRankData"
MonopolyRollDiceREQ"Û
MonopolyRollDiceRSP)
	self_info (2.pk.MonopolyPlayerInfo'
	rank_data (2.pk.MonopolyRankData
dice (@
position_reward (2'.pk.MonopolyRollDiceRSP.PostitionReward>
score_reward (2(.pk.MonopolyRollDiceRSP.TotalScoreReward
code (2.pk.ErrCodex
PostitionReward
reward_type (
diamond (
chest_diamond_rate (
item_id (

item_count (K
TotalScoreReward

free_count (
item_id (

item_count ("2
GetMonopolyRankDataREQ
	pre_round (:false"T
GetMonopolyRankDataRSP
	pre_round ('
	rank_data (2.pk.MonopolyRankData"q
GiveMonopolyRankRewardRSP
score (
rank (
item_id (

item_count (

free_count (".
SetMonopolyRollMultipleREQ
multiple ("b
SetMonopolyRollMultipleRSP)
	self_info (2.pk.MonopolyPlayerInfo
code (2.pk.ErrCode"
GetDailyTaskInfoREQ"P
GetDailyTaskInfoRSP
server_time ($
	task_info (2.pk.DailyTaskItem",
ReceiveDailyTaskRewardREQ
task_id ("\
ReceiveDailyTaskRewardRSP
code (2.pk.ErrCode$
	task_info (2.pk.DailyTaskItem">
UpdateDailyTaskInfoRSP$
	task_info (2.pk.DailyTaskItem",
GetAvatarThumbUpDataREQ
	series_id ("·
GetAvatarThumbUpDataRSP
	series_id (:

total_data (2&.pk.GetAvatarThumbUpDataRSP.AvatarInfo
self_thumb_up_avatars (.

AvatarInfo
	avatar_id (
count ("J
ThumbUpAvatarREQ
	series_id (
	avatar_id (
thumb_up ("e
ThumbUpAvatarRSP
	series_id (
	avatar_id (
thumb_up (
code (2.pk.ErrCode"a
LuckyBoxRankPlayerBrief
uid (
name (	
avatar (	
score (
rank ("¦
LuckyBoxRankData3
self_rank_data (2.pk.LuckyBoxRankPlayerBrief6
player_rank_datas (2.pk.LuckyBoxRankPlayerBrief
round (
round_end_time ("
GetLuckyBoxInfoREQ"¥
GetLuckyBoxInfoRSP#
fetched_public_reward_round (
public_reward_round ($
public_reward_round_end_time ('
	rank_data (2.pk.LuckyBoxRankData"&
LuckyBoxDrawRewardREQ
count ("w
LuckyBoxDrawRewardRSP
diamond (
gold ($
reward_items (2.pk.RewardItem
code (2.pk.ErrCode"2
GetLuckyBoxRankDataREQ
	pre_round (:false"T
GetLuckyBoxRankDataRSP
	pre_round ('
	rank_data (2.pk.LuckyBoxRankData"_
FetchLuckyBoxRankRewardRSP
score (
rank ($
reward_items (2.pk.RewardItem"L
GiveLuckyBoxREQ
room_id (
to_uids (
to_public_count ("D
GiveLuckyBoxRSP
return_diamond (
code (2.pk.ErrCode"L
GiveLuckyBoxBRC
from_uid (
to_uids (
return_diamond ("
FetchLuckyBoxPublicRewardREQ"P
FetchLuckyBoxPublicRewardRSP
fetch_box_count (
fetch_box_round (*Ò
RedEnvelopeItemType!
RED_ENVELOPE_ITEM_TYPE_DRAGON 
RED_ENVELOPE_ITEM_TYPE_TIGER
RED_ENVELOPE_ITEM_TYPE_FISH!
RED_ENVELOPE_ITEM_TYPE_BRANCH"
RED_ENVELOPE_ITEM_TYPE_SLOGAN1"
RED_ENVELOPE_ITEM_TYPE_SLOGAN2"
RED_ENVELOPE_ITEM_TYPE_SLOGAN3"
RED_ENVELOPE_ITEM_TYPE_SLOGAN4"
RED_ENVELOPE_ITEM_TYPE_SLOGAN5	*O
TimingRewardType
TIMING_REWARD_TYPE_DIAMOND 
TIMING_REWARD_TYPE_GOLD*g

ActivityID$
 ACTIVITY_ID_ACCUMULATED_RECHARGE
ACTIVITY_ID_MONOPOLY
ACTIVITY_ID_LUCKY_BOX