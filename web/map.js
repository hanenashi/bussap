/* Leaflet map controller. All stop labels are inserted as text, never as HTML. */
(() => {
  const operatorNames = { chuo: "北海道中央バス", jr: "JR北海道バス", jotetsu: "じょうてつ" };
  let map, layer, onStopChosen, operator = "all", requestSerial = 0, sheetSerial = 0;
  let activeStop = null, sheetDate = null;
  const $ = id => document.getElementById(id);
  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  };
  const nowInTokyo = () => {
    const parts = Object.fromEntries(new Intl.DateTimeFormat("en-US", {timeZone:"Asia/Tokyo",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hourCycle:"h23"}).formatToParts(new Date()).filter(part => part.type !== "literal").map(part => [part.type, part.value]));
    return {date:`${parts.year}-${parts.month}-${parts.day}`,time:`${parts.hour}:${parts.minute}`};
  };
  const nextDay = iso => {
    const day = new Date(`${iso}T12:00:00+09:00`); day.setUTCDate(day.getUTCDate() + 1);
    const parts = Object.fromEntries(new Intl.DateTimeFormat("en-US", {timeZone:"Asia/Tokyo",year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(day).filter(part => part.type !== "literal").map(part => [part.type, part.value]));
    return `${parts.year}-${parts.month}-${parts.day}`;
  };
  const displayTime = time => { const [hour, minute] = time.split(":"); return `${String(Number(hour)%24).padStart(2,"0")}:${minute}`; };
  function status(message, error=false) { const node=$("map-status"); node.hidden=!message; node.textContent=message||""; node.classList.toggle("error",error); }

  function init(chosen) {
    onStopChosen = chosen;
    map = L.map("map", {zoomControl:false, preferCanvas:true, zoomSnap:0.5}).setView([43.066,141.352],15);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      minZoom:10,maxZoom:19,maxNativeZoom:19,attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
      updateWhenIdle:true,keepBuffer:1
    }).addTo(map);
    layer=L.layerGroup().addTo(map);
    map.on("moveend",loadFeatures);
    map.on("tileerror",()=>status("地図の背景を読み込めませんでした。停留所は表示できます。",true));
    $("locate-button").addEventListener("click",locate);
    map.on("click",showIntro);
    showIntro();
    loadFeatures();
  }
  function showIntro() {
    activeStop=null; ++sheetSerial;
    const content=$("sheet-content");content.replaceChildren();
    content.append(el("h2","sheet-title","札幌のバス停"),el("p","sheet-subtitle","地図の点をタップして、乗る場所と時刻を確認できます。"));
    const legend=el("div","sheet-legend");
    for (const [key,label] of [["chuo","中央"],["jr","JR"],["jotetsu","じょうてつ"]]) {
      const item=el("span","sheet-legend-item");item.append(el("i",`legend-dot ${key}`),document.createTextNode(label));legend.append(item);
    }
    content.append(legend);$("map-sheet").hidden=false;
  }
  async function loadFeatures() {
    if (!map) return;
    const serial=++requestSerial, bounds=map.getBounds();
    const bbox=[bounds.getSouth(),bounds.getWest(),bounds.getNorth(),bounds.getEast()].map(n=>n.toFixed(6)).join(",");
    const params=new URLSearchParams({bbox,zoom:String(Math.round(map.getZoom())),operator});
    try {
      const response=await fetch(`/api/map-stops?${params}`,{cache:"no-store"});
      const data=await response.json();
      if (!response.ok) throw Error(data.error||"map API error");
      if (serial!==requestSerial) return;
      layer.clearLayers();
      for (const feature of data.features) addFeature(feature);
      status(data.warnings.length ? "JRの地図データを更新できていません。中央・じょうてつを表示中。" :
        data.total_stops ? "" : "この範囲に停留所がありません。地図を動かすか、会社を切り替えてください。");
    } catch {
      if (serial===requestSerial) status("停留所を読み込めませんでした。地図を動かして再試行してください。",true);
    }
  }
  function addFeature(feature) {
    const isCluster=feature.type==="cluster";
    const kind=isCluster ? (feature.operators.length===1 ? feature.operators[0] : "mixed") : feature.operator;
    const marker=L.marker([feature.lat,feature.lon],{
      icon:L.divIcon({className:"",html:`<span class="bus-marker ${kind} ${isCluster?"cluster":""}">${isCluster?feature.count:""}</span>`,iconSize:[36,36],iconAnchor:[18,18]}),
      title:isCluster ? `${feature.count}か所の乗り場` : `${feature.name} ${operatorNames[feature.operator]}`
    }).addTo(layer);
    marker.on("click",()=>{
      if (!isCluster) return showStop(feature);
      if (feature.members.length) showCluster(feature);
      else map.setView([feature.lat,feature.lon],Math.min(19,map.getZoom()+2));
    });
  }
  function openSheet() { $("map-sheet").hidden=false; $("map-sheet").scrollIntoView({block:"nearest",behavior:"smooth"}); }
  function showCluster(feature) {
    activeStop=null; ++sheetSerial;
    const content=$("sheet-content"); content.replaceChildren();
    content.append(el("h2","sheet-title",`${feature.count}か所の乗り場`),el("p","sheet-subtitle","乗る場所を選んでください。"));
    const list=el("div","sheet-stop-list");
    for (const stop of feature.members) {
      const button=el("button","sheet-stop-button");button.type="button";
      button.append(el("strong","",stop.name),el("small","",`${operatorNames[stop.operator]}${stop.boarding_position?` · ${stop.boarding_position}番のりば`:""}`));
      button.addEventListener("click",()=>showStop(stop));list.append(button);
    }
    content.append(list);openSheet();
  }
  function showStop(stop) {
    activeStop=stop;sheetDate=nowInTokyo().date;renderStopSheet();openSheet();
  }
  function renderStopSheet() {
    const stop=activeStop, serial=++sheetSerial;
    const content=$("sheet-content");content.replaceChildren();
    const title=el("h2","sheet-title",`${stop.name}${stop.boarding_position?` · ${stop.boarding_position}番のりば`:""}`);
    const subtitle=el("p","sheet-subtitle",`${operatorNames[stop.operator]}${stop.coordinate_kind==="station"?" · 停留所の代表位置":""}`);
    const dateControls=el("div","sheet-date-controls");
    const today=nowInTokyo().date;
    for (const [label,date] of [["今日",today],["明日",nextDay(today)]]) {
      const button=el("button",`date-button${sheetDate===date?" active":""}`,label);button.type="button";
      button.addEventListener("click",()=>{sheetDate=date;renderStopSheet()});dateControls.append(button);
    }
    const heading=el("h3","sheet-heading","次のバス");
    const results=el("div","sheet-departures");
    const action=el("button","sheet-action",stop.operator==="jr"?"路線を選ぶ ›":"時刻表を見る ›");action.type="button";
    action.addEventListener("click",()=>onStopChosen(stop,sheetDate));
    content.append(title,subtitle,dateControls,heading,results,action);
    if (stop.operator==="jr") {
      results.append(el("p","sheet-message","JRは路線と行先を選ぶと時刻を表示します。"));
      return;
    }
    results.append(el("p","sheet-message","時刻を読み込んでいます…"));
    const params=new URLSearchParams({operator:stop.operator,stop:stop.id.split(":")[1],date:sheetDate,
      after:sheetDate===today?nowInTokyo().time:"00:00",limit:"2"});
    fetch(`/api/departures?${params}`,{cache:"no-store"}).then(async response=>{
      const data=await response.json();if (!response.ok) throw Error();
      if (serial!==sheetSerial) return;
      results.replaceChildren();
      if (data.status==="outside_feed_coverage") {results.append(el("p","sheet-message","この日付の時刻表はありません。"));return;}
      if (!data.departures.length) {results.append(el("p","sheet-message","この時間以降のバスはありません。"));return;}
      for (const departure of data.departures) {
        const row=el("div","sheet-departure");
        const route=departure.route||"路線名なし";
        row.append(el("strong","",displayTime(departure.scheduled_time)),el("span","",`${route.split(/[・･]/)[0]}　${departure.destination||"行先不明"}`));
        results.append(row);
      }
    }).catch(()=>{if(serial===sheetSerial){results.replaceChildren(el("p","sheet-message","時刻を読み込めませんでした。"))}});
  }
  function locate() {
    if (!navigator.geolocation) {status("このブラウザでは現在地を取得できません。",true);return;}
    status("現在地を確認しています…");
    navigator.geolocation.getCurrentPosition(position=>{
      status("");map.setView([position.coords.latitude,position.coords.longitude],16);
      L.circleMarker([position.coords.latitude,position.coords.longitude],{radius:7,color:"#fff",weight:2,fillColor:"#2378c4",fillOpacity:1}).addTo(map);
    },()=>status("現在地を取得できませんでした。位置情報の許可を確認してください。",true),{enableHighAccuracy:false,timeout:10000,maximumAge:60000});
  }
  function show() { if(map){requestAnimationFrame(()=>{map.invalidateSize();loadFeatures()})} }
  function setOperator(value) {operator=value;loadFeatures()}
  function focus(stop) {if(map&&stop.lat!=null&&stop.lon!=null) map.setView([stop.lat,stop.lon],16)}
  window.BUSSAPMap={init,show,setOperator,focus};
})();
