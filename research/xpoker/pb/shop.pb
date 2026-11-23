
ˆ

shop.protopk
base.proto"z
PurchaseVipREQ,
	vip_level (2.pk.VIPLevel:VIP_LEVEL_0:
vip_card_type (2.pk.VIPCardType:VIP_CARD_TYPE_NONE"T
PurchaseVipRSP
vip (2.pk.VipInfo
code (2.pk.ErrCode
toast ("N
RemainingTimeBankAmountRSP

vip_amount (:0
package_amount (:0";
PurchaseShopPackageREQ!
type (2.pk.ShopPackageType"V
PurchaseShopPackageRSP!
info (2.pk.ShopPackageInfo
code (2.pk.ErrCode"9
UpdateShopPackageBRC!
info (2.pk.ShopPackageInfo")
DiamondExchangeGoldREQ
diamond ("X
DiamondExchangeGoldRSP
spend_diamond (
gold (
code (2.pk.ErrCode"%
ScoreExchangeGoldREQ
score ("T
ScoreExchangeGoldRSP
spend_score (
gold (
code (2.pk.ErrCode"a
RechargeRSP!

money_kind (2.pk.MoneyKind
recharge_value (
remaining_value ("
QueryNamePriceREQ""
QueryNamePriceRSP
price ("(
PurchaseTableThemeREQ
item_id ("G
PurchaseTableThemeRSP
item_id (
ret_code (2.pk.ErrCode"¤
PurchaseVipPackageREQ
item_id (,
	vip_level (2.pk.VIPLevel:VIP_LEVEL_0:
vip_card_type (2.pk.VIPCardType:VIP_CARD_TYPE_NONE
count (:0"¿
PurchaseVipPackageRSP
item_id (,
	vip_level (2.pk.VIPLevel:VIP_LEVEL_0:
vip_card_type (2.pk.VIPCardType:VIP_CARD_TYPE_NONE
count (:0
code (2.pk.ErrCode