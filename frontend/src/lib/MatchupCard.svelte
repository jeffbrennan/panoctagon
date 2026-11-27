<script lang="ts">
  import type { Matchup } from './types';
  import { delta, fighterHref, inches, label, odds } from './format';
  import Headshot from './Headshot.svelte';
  let { fight, main = false }: { fight: Matchup; main?: boolean } = $props();
  let expanded = $state(false);
  const recordCount = (record: string) => record.split('-').reduce((sum, n) => sum + Number(n), 0);
  let fighters = $derived([
    {
      uid: fight.fighter1_uid,
      name: fight.fighter1_name,
      record: fight.fighter1_record,
      reach: fight.fighter1_reach,
      height: fight.fighter1_height,
      stance: fight.fighter1_stance,
      odds: fight.fighter1_closing_odds,
      total: fight.fighter1_total_fights ?? recordCount(fight.fighter1_record),
    },
    {
      uid: fight.fighter2_uid,
      name: fight.fighter2_name,
      record: fight.fighter2_record,
      reach: fight.fighter2_reach,
      height: fight.fighter2_height,
      stance: fight.fighter2_stance,
      odds: fight.fighter2_closing_odds,
      total: fight.fighter2_total_fights ?? recordCount(fight.fighter2_record),
    },
  ]);
</script>

<article class="matchup" class:main-event={main}>
  <div class="matchup-meta">
    <span>{label(fight.fight_division)}</span>{#if main}<span class="badge dark">Main event</span
      >{:else if fight.fight_type === 'TITLE'}<span class="badge">Title bout</span>{/if}
  </div>
  <div class="matchup-fighters">
    {#each fighters as f, i}
      {#if i === 1}<span class="versus" aria-label="versus">vs</span>{/if}
      <div class="matchup-fighter" class:opponent={i === 1}>
        <Headshot uid={f.uid} name={f.name} />
        <div class="fighter-identity">
          <a class="fighter-name" href={fighterHref(f.uid)} data-fighter={f.uid}>{f.name}</a>
          <div class="fighter-subline">
            <span class="record">{f.record}</span>{#if f.odds != null}<span
                class="odds"
                class:favorite={f.odds < 0}>{odds(f.odds)}</span
              >{/if}
          </div>
        </div>
      </div>
    {/each}
  </div>
  <div class="comparison" class:expanded>
    {#each fighters as f, i}
      <div class="fighter-metrics">
        <div>
          <span>Reach</span><strong>{inches(f.reach)}</strong><small
            >{delta(f.reach, fighters[1 - i].reach, '″')}</small
          >
        </div>
        <div>
          <span>Height</span><strong>{inches(f.height)}</strong><small
            >{delta(f.height, fighters[1 - i].height, '″')}</small
          >
        </div>
        <div><span>Stance</span><strong>{f.stance || '—'}</strong></div>
        <div>
          <span>UFC fights</span><strong>{f.total}</strong><small
            >{delta(f.total, fighters[1 - i].total)}</small
          >
        </div>
      </div>
    {/each}
  </div>
  <button class="compare-toggle" aria-expanded={expanded} onclick={() => (expanded = !expanded)}
    >{expanded ? 'Hide comparison' : 'Compare fighters'}<span aria-hidden="true"
      >{expanded ? '−' : '+'}</span
    ></button
  >
</article>
