<script lang="ts">
  let { uid, name, large = false }: { uid: string; name: string; large?: boolean } = $props();
  let failed = $state(false);
  let loaded = $state(false);
  $effect(() => {
    uid;
    failed = false;
    loaded = false;
  });
</script>

<div class="headshot" class:large>
  {#if !failed}
    <img
      src={`/api/fighter/${encodeURIComponent(uid)}/headshot`}
      alt=""
      loading="lazy"
      decoding="async"
      onerror={() => (failed = true)}
      onload={() => (loaded = true)}
      class:loaded
    />
  {/if}
  {#if !loaded || failed}
    <span aria-hidden="true"
      >{name
        .split(' ')
        .map((n) => n[0])
        .slice(0, 2)
        .join('')}</span
    >
  {/if}
</div>

<style>
  .headshot {
    position: relative;
  }
  img {
    position: absolute;
    inset: 0;
    opacity: 0;
    transition: opacity 140ms ease;
  }
  img.loaded {
    opacity: 1;
  }
</style>
