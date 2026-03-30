import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const year = ref(new Date().getFullYear())
  const curMonth = ref(new Date().getMonth() + 1)
  const units = ref([])   // loaded once from API

  function setYear(y) { year.value = y }
  function setUnits(list) { units.value = list }

  return { year, curMonth, units, setYear, setUnits }
})
