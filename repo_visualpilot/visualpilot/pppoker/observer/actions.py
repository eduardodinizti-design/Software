"""Visible action badges, not a reconstructed betting history."""
from ..replay.vision import occupied_labels,box_of


def read_actions(rows,rgb):
    height,width=rgb.shape[:2];players=occupied_labels(rows,rgb);result=[]
    for poly,text,score in rows:
        action=text.strip().lower()
        box=box_of(poly);cx=box[0]+box[2]/2;cy=box[1]+box[3]/2
        if action not in {'fold','call','raise','check','bet','all-in','allin'} or score<.90 or not .10*height<cy<.89*height:continue
        options=[]
        for player in players:
            x,y,w,h=player['box'];px=x+w/2;py=y+h/2
            if 0<py-cy<.13*height and abs(px-cx)<.15*width:
                options.append((abs(px-cx)/width+(py-cy)/height,player))
        options.sort(key=lambda o:o[0]);player=None
        if options and (len(options)==1 or options[1][0]-options[0][0]>.025):player=options[0][1]
        result.append(dict(action='all-in' if action=='allin' else action,player_label=player['nickname'] if player else None,
            player_box=player['box'] if player else None,badge_box=box,confidence=float(score),
            evidence='visible_badge',amount=None,player_id=None,performed_at=None,action_street=None))
    return result
