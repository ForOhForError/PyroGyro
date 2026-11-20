<script setup>
const props = defineProps({
  TYPE: String,
  name: String
})
</script>

<template>
  <div>
    <h2>{{ name }}</h2>
    <h3>{{ count }}</h3>
  </div>
</template>