<?xml version="1.0" encoding="UTF-8"?>
<tileset version="1.10" tiledversion="1.10.2" name="ground" tilewidth="16" tileheight="16" spacing="1" margin="0" tilecount="64" columns="8">
 <image source="tiles.png" width="135" height="135"/>
 <tile id="5">
  <properties>
   <property name="footstep" value="grass"/>
   <property name="comment" value="ignored"/>
  </properties>
  <objectgroup draworder="index" id="2">
   <object id="1" x="0" y="8" width="16" height="8"/>
  </objectgroup>
 </tile>
 <tile id="9">
  <objectgroup draworder="index" id="2">
   <object id="1" x="0" y="0">
    <polygon points="0,0 16,0 16,16"/>
   </object>
  </objectgroup>
 </tile>
 <tile id="17">
  <objectgroup draworder="index" id="2">
   <object id="1" x="0" y="0" width="16" height="16"/>
  </objectgroup>
 </tile>
 <wangsets>
  <wangset name="ground" type="corner" tile="-1">
   <wangcolor name="grass" color="#00ff00" tile="-1" probability="1"/>
   <wangcolor name="dirt" color="#aa5500" tile="-1" probability="1"/>
   <wangtile tileid="0" wangid="0,1,0,1,0,1,0,1"/>
   <wangtile tileid="1" wangid="0,2,0,2,0,2,0,2"/>
  </wangset>
 </wangsets>
</tileset>
