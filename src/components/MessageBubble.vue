<script setup>
defineProps({
  role: {
    type: String,
    required: true
  },
  content: {
    type: String,
    default: ''
  }
})
</script>

<template>
  <div v-if="role === 'system'" class="bubble-system">
    <span class="bubble-system__inner">{{ content }}</span>
  </div>

  <div
    v-else
    class="bubble-row"
    :class="[`bubble-row--${role}`]"
  >
    <div class="bubble-avatar" v-if="role === 'ai'">
      <svg width="40" height="40" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
        <g filter="url(#filter0_dd_1001_389)">
          <path d="M3 18.8743C3 9.55486 10.5549 2 19.8743 2C29.1937 2 36.7485 9.55486 36.7485 18.8743C36.7485 28.1937 29.1937 35.7485 19.8743 35.7485C10.5549 35.7485 3 28.1937 3 18.8743Z" fill="#DBEAFE" shape-rendering="crispEdges"/>
          <path d="M24.04 15.5417H15.7085C14.7882 15.5417 14.0422 16.2877 14.0422 17.208V22.2069C14.0422 23.1271 14.7882 23.8732 15.7085 23.8732H24.04C24.9603 23.8732 25.7063 23.1271 25.7063 22.2069V17.208C25.7063 16.2877 24.9603 15.5417 24.04 15.5417Z" fill="#2563EB"/>
          <path d="M19.0411 18.0411H17.7914C17.5613 18.0411 17.3748 18.2276 17.3748 18.4577V19.7074C17.3748 19.9375 17.5613 20.124 17.7914 20.124H19.0411C19.2712 20.124 19.4577 19.9375 19.4577 19.7074V18.4577C19.4577 18.2276 19.2712 18.0411 19.0411 18.0411Z" fill="white"/>
          <path d="M21.9571 18.0411H20.7074C20.4773 18.0411 20.2908 18.2276 20.2908 18.4577V19.7074C20.2908 19.9375 20.4773 20.124 20.7074 20.124H21.9571C22.1872 20.124 22.3737 19.9375 22.3737 19.7074V18.4577C22.3737 18.2276 22.1872 18.0411 21.9571 18.0411Z" fill="white"/>
          <path d="M21.5406 21.3737H18.208C17.9779 21.3737 17.7914 21.5602 17.7914 21.7903C17.7914 22.0204 17.9779 22.2069 18.208 22.2069H21.5406C21.7706 22.2069 21.9571 22.0204 21.9571 21.7903C21.9571 21.5602 21.7706 21.3737 21.5406 21.3737Z" fill="#93C5FD"/>
          <path d="M20.2908 13.0422H19.4577C18.9976 13.0422 18.6245 13.4152 18.6245 13.8754V14.7085C18.6245 15.1686 18.9976 15.5417 19.4577 15.5417H20.2908C20.751 15.5417 21.124 15.1686 21.124 14.7085V13.8754C21.124 13.4152 20.751 13.0422 20.2908 13.0422Z" fill="#2563EB"/>
          <path d="M20.2908 12.6256C20.2908 12.3956 20.1043 12.2091 19.8743 12.2091C19.6442 12.2091 19.4577 12.3956 19.4577 12.6256V13.4588C19.4577 13.6889 19.6442 13.8754 19.8743 13.8754C20.1043 13.8754 20.2908 13.6889 20.2908 13.4588V12.6256Z" fill="#2563EB"/>
          <path d="M19.4577 13.0422C19.9178 13.0422 20.2908 12.6692 20.2908 12.2091C20.2908 11.7489 19.9178 11.3759 19.4577 11.3759C18.9976 11.3759 18.6245 11.7489 18.6245 12.2091C18.6245 12.6692 18.9976 13.0422 19.4577 13.0422Z" fill="#60A5FA"/>
          <path d="M14.0422 18.0411C14.0422 17.581 13.6692 17.208 13.2091 17.208C12.7489 17.208 12.3759 17.581 12.3759 18.0411V19.7074C12.3759 20.1675 12.7489 20.5406 13.2091 20.5406C13.6692 20.5406 14.0422 20.1675 14.0422 19.7074V18.0411Z" fill="#93C5FD"/>
          <path d="M27.3726 18.0411C27.3726 17.581 26.9996 17.208 26.5395 17.208C26.0793 17.208 25.7063 17.581 25.7063 18.0411V19.7074C25.7063 20.1675 26.0793 20.5406 26.5395 20.5406C26.9996 20.5406 27.3726 20.1675 27.3726 19.7074V18.0411Z" fill="#93C5FD"/>
        </g>
        <defs>
          <filter id="filter0_dd_1001_389" x="0" y="0" width="39.7485" height="39.7485" filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB">
            <feFlood flood-opacity="0" result="BackgroundImageFix"/>
            <feColorMatrix in="SourceAlpha" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 127 0" result="hardAlpha"/>
            <feMorphology radius="1" operator="erode" in="SourceAlpha" result="effect1_dropShadow_1001_389"/>
            <feOffset dy="1"/>
            <feGaussianBlur stdDeviation="1"/>
            <feComposite in2="hardAlpha" operator="out"/>
            <feColorMatrix type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0.1 0"/>
            <feBlend mode="normal" in2="BackgroundImageFix" result="effect1_dropShadow_1001_389"/>
            <feColorMatrix in="SourceAlpha" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 127 0" result="hardAlpha"/>
            <feOffset dy="1"/>
            <feGaussianBlur stdDeviation="1.5"/>
            <feComposite in2="hardAlpha" operator="out"/>
            <feColorMatrix type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0.1 0"/>
            <feBlend mode="normal" in2="effect1_dropShadow_1001_389" result="effect2_dropShadow_1001_389"/>
            <feBlend mode="normal" in="SourceGraphic" in2="effect2_dropShadow_1001_389" result="shape"/>
          </filter>
        </defs>
      </svg>
    </div>

    <div class="bubble" :class="[`bubble--${role}`]">
      <div class="bubble__content">{{ content }}</div>
    </div>

    <div class="bubble-avatar bubble-avatar--user" v-if="role === 'user'">
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
        <circle cx="9" cy="6" r="3" fill="rgba(255,255,255,0.9)"/>
        <path d="M4.5 12C4.5 10.343 6.343 9 9 9C11.657 9 13.5 10.343 13.5 12" stroke="#fff" stroke-width="1.5"/>
      </svg>
    </div>
  </div>
</template>

<style scoped>
.bubble-row {
  display: flex;
  flex-direction: row;
  align-items: flex-end;
  gap: 9.38px;
  width: 100%;
  margin-bottom: 20px;
}
.bubble-row--user {
  justify-content: flex-end;
}

.bubble-avatar {
  width: 40px;
  height: 40px;
  display: flex;
  flex-direction: row;
  justify-content: center;
  align-items: center;
  padding: 0;
  border-radius: 1.58276e+07px;
  flex: none;
  order: 0;
  flex-grow: 0;
}
.bubble-avatar--user {
  background: #615FFF;
}

.bubble {
  padding: 11.25px 15px;
  max-width: calc(100% - 50px);
  box-shadow: 0px 1px 3px rgba(0, 0, 0, 0.1), 0px 1px 2px -1px rgba(0, 0, 0, 0.1);
  font-size: 14.0625px;
  line-height: 23px;
  word-break: break-word;
  white-space: pre-wrap;
}
.bubble--ai {
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 15px 15px 15px 5.375px;
  color: #1A1D23;
}
.bubble--user {
  background: #2563EB;
  border-radius: 15px 15px 5.375px 15px;
  color: #fff;
}

.bubble-system {
  text-align: center;
  margin: 16px 0;
}
.bubble-system__inner {
  display: inline-block;
  padding: 6px 12px;
  font-size: 12px;
  color: #8a90a2;
  background: rgba(0, 0, 0, 0.04);
  border-radius: 999px;
}
</style>