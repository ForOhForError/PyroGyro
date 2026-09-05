<script setup>
import { BaklavaEditor, useBaklava } from "@baklavajs/renderer-vue";
import "@baklavajs/themes/dist/syrup-dark.css";
import MyNode from "./nodes";
const baklava = useBaklava();
var socket;
baklava.editor.registerNodeType(MyNode);

baklava.editor.hooks.save.subscribe("sendState", (state, editor) => {
  console.log(state);
  if(socket) {
    socket.send(JSON.stringify(state));
  }
});

function saveGraph() {
  baklava.editor.save();
}

function valueToColor(value) {
  switch (typeof(value)) {
    case 'string':
      return value;
    case 'number':
      inverse = 255*(1.0-value);
      return ["rgb(",inverse,",",inverse,",",inverse,")"].join("");
  }
}

function vec2ToTranslate(x, y, size) {
  return ["translate(",size*x,"px,",size*y,"px)"].join("")
}

function onSvgClick(event) {
  event.preventDefault();
  console.log("hi")
}
try {
  var loc = window.location, new_uri;
  var ws_uri;
  if (loc.protocol === "https:") {
      ws_uri = "wss:";
  } else {
      ws_uri = "ws:";
  }
  ws_uri += "//" + loc.host;
  ws_uri += loc.pathname + "/ws";
  socket = new WebSocket(ws_uri);
  // Connection opened
  socket.addEventListener("open", (event) => {
    socket.send("Hello Server!");
  });
  // Listen for messages
  socket.addEventListener("message", (event) => {
    messageObj = JSON.parse(event.data);
    var pad = document.getElementById("gamepad");
    switch (messageObj.type) {
      case "float":
        padPart = pad.contentDocument.getElementById(messageObj.source);
        padPart.style.fill=valueToColor(messageObj.value);
        break;
      case "vec2":
        padPart = pad.contentDocument.getElementById(messageObj.source);
        padPart.style.transform = vec2ToTranslate(messageObj.x,messageObj.y, padPart.getBoundingClientRect().width*0.3);
        break;
    }
  });
  var pad = document.getElementById("gamepad");
  //pad.addEventListener('click', onSvgClick);
} catch (error) {
  console.error(error);
}
</script>

<template>
  <div style="height:800px">
    <button @click="saveGraph()">Save</button>
    <BaklavaEditor :view-model="baklava" />
    <object id="gamepad" data="gamepad.svg" width="500px" type="image/svg+xml"></object>
  </div>
</template>

<style scoped></style>
