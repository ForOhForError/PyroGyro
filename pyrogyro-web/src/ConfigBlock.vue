<script setup>
const props = defineProps({
  TYPE: String,
  name: String,
  input_slots: Array,
  output_slots: Array,
  config_slots: Array
})
</script>

<template>
  <div>
    <h2>{{ name }}</h2>
    <h3>{{ TYPE }}</h3>
  </div>
</template>