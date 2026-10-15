<script lang="ts">
  let { uid, name, large = false }: { uid: string; name: string; large?: boolean } = $props();
  let failed = $state(false);
  $effect(() => {
    uid;
    failed = false;
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
    />
  {:else}
    <span aria-hidden="true"
      >{name
        .split(' ')
        .map((n) => n[0])
        .slice(0, 2)
        .join('')}</span
    >
  {/if}
</div>
