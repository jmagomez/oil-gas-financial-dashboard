/* ================= Camada de acessibilidade e usabilidade =================
   Os graficos sao <canvas>: sem isto, leitor de tela nao enxerga nada. Cada
   grafico ganha rotulo, e uma tabela equivalente e mantida em sincronia com
   os dados reais do Chart.js. Cabecalhos de tabela viram operaveis por teclado. */
(function(){
  'use strict';

  /* -- 1. Movimento reduzido: respeita a preferencia do sistema -- */
  var mqReduzir = window.matchMedia('(prefers-reduced-motion: reduce)');
  function aplicarMovimento(){
    if(!window.Chart) return;
    Chart.defaults.animation = mqReduzir.matches
      ? false
      : {duration:550, easing:'easeOutQuart'};
  }
  aplicarMovimento();
  if(mqReduzir.addEventListener) mqReduzir.addEventListener('change', aplicarMovimento);

  /* -- 2. Regiao de status para anunciar mudancas de filtro/periodo -- */
  var status = document.createElement('div');
  status.className = 'sr-only';
  status.id = 'a11yStatus';
  status.setAttribute('role','status');
  status.setAttribute('aria-live','polite');
  status.setAttribute('aria-atomic','true');
  document.body.appendChild(status);
  var tAnuncio = null;
  window.anunciar = function(msg){
    clearTimeout(tAnuncio);
    status.textContent = '';
    tAnuncio = setTimeout(function(){ status.textContent = msg; }, 80);
  };

  /* -- 3. Descricao textual dos graficos -- */
  function rotuloDoCanvas(canvas){
    var card = canvas.closest ? canvas.closest('.card') : null;
    if(!card) return '';
    var h = card.querySelector('h3');
    var n = card.querySelector('.note');
    return [h && h.textContent.trim(), n && n.textContent.trim()]
      .filter(Boolean).join(' — ');
  }

  function valorLegivel(v){
    if(v === null || v === undefined || v === '') return 'sem dado';
    if(typeof v === 'object'){
      var partes = [];
      if('x' in v) partes.push('x ' + v.x);
      if('y' in v) partes.push('y ' + v.y);
      if('r' in v) partes.push('tamanho ' + v.r);
      return partes.length ? partes.join(', ') : 'sem dado';
    }
    return String(v);
  }

  function esc(t){
    return String(t).replace(/[&<>"]/g, function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];
    });
  }

  function tabelaEquivalente(chart){
    var d = chart.data || {};
    var labels = d.labels || [];
    var sets = (d.datasets || []).filter(function(s){ return !s.hidden; });
    if(!sets.length) return '';
    if(!labels.length){
      labels = (sets[0].data || []).map(function(_, i){ return 'Item ' + (i + 1); });
    }
    var h = '<table><caption>Equivalente em tabela dos dados do grafico</caption>'
          + '<thead><tr><th scope="col">Categoria</th>';
    sets.forEach(function(s){ h += '<th scope="col">' + esc(s.label || 'Serie') + '</th>'; });
    h += '</tr></thead><tbody>';
    labels.forEach(function(l, i){
      h += '<tr><th scope="row">' + esc(l) + '</th>';
      sets.forEach(function(s){
        h += '<td>' + esc(valorLegivel((s.data || [])[i])) + '</td>';
      });
      h += '</tr>';
    });
    return h + '</tbody></table>';
  }

  function descrever(chart){
    var c = chart.canvas;
    if(!c || !c.parentElement) return;
    c.setAttribute('role','img');
    var rot = rotuloDoCanvas(c);
    if(rot) c.setAttribute('aria-label', rot + '. Equivalente em tabela logo apos o grafico.');
    var alvo = c.parentElement.querySelector('[data-chart-table]');
    if(!alvo){
      alvo = document.createElement('div');
      alvo.className = 'sr-only';
      alvo.setAttribute('data-chart-table','');
      c.parentElement.appendChild(alvo);
    }
    var novo = tabelaEquivalente(chart);
    if(alvo.innerHTML !== novo) alvo.innerHTML = novo;
  }

  if(window.Chart && Chart.register){
    Chart.register({
      id: 'acessibilidade',
      // afterUpdate, nao afterRender: afterRender dispara a cada FRAME da
      // animacao (~33x por grafico a 550ms), e reconstruir a tabela
      // equivalente a cada frame trava a thread principal. afterUpdate
      // dispara uma vez por mudanca de dados, que e quando a tabela muda.
      afterUpdate: function(chart){
        try { descrever(chart); } catch(e){ /* nunca derrubar o grafico */ }
      }
    });
  }

  /* -- 4. Cabecalhos de tabela operaveis por teclado -- */
  function upgradeCabecalhos(){
    document.querySelectorAll('table thead th').forEach(function(th){
      if(!th.getAttribute('scope')) th.setAttribute('scope','col');
      var clicavel = typeof th.onclick === 'function';
      if(!clicavel) return;
      if(!th.hasAttribute('tabindex')) th.setAttribute('tabindex','0');
      var txt = th.textContent || '';
      th.setAttribute('aria-sort',
        th.classList.contains('sorted')
          ? (txt.indexOf('▲') >= 0 ? 'ascending' : 'descending')
          : 'none');
      if(!th.dataset.kbLigado){
        th.dataset.kbLigado = '1';
        th.addEventListener('keydown', function(ev){
          if(ev.key === 'Enter' || ev.key === ' ' || ev.key === 'Spacebar'){
            ev.preventDefault();
            th.click();
            var rotulo = (th.textContent || '').replace(/[▲▼↕]/g,'').trim();
            window.anunciar('Ordenado por ' + rotulo + '.');
          }
        });
      }
    });
  }

  /* -- 5. Tabelas de dados: legenda e contagem anunciada -- */
  function upgradeTabelas(){
    var t = document.getElementById('dataTable');
    if(t && !t.querySelector('caption')){
      var cap = document.createElement('caption');
      cap.className = 'sr-only';
      cap.textContent = 'Indicadores primarios e derivados por empresa no periodo selecionado. '
                      + 'Use Tab para percorrer os cabecalhos e Enter para ordenar.';
      t.insertBefore(cap, t.firstChild);
    }
    var h = document.getElementById('tblHeat');
    if(h && !h.querySelector('caption')){
      var cap2 = document.createElement('caption');
      cap2.className = 'sr-only';
      cap2.textContent = 'Mapa de calor comparativo entre empresas. A intensidade da cor '
                       + 'acompanha o valor; os numeros estao em cada celula.';
      h.insertBefore(cap2, h.firstChild);
    }
  }

  /* -- 6. Link para pular direto ao conteudo -- */
  function skipLink(){
    if(document.querySelector('.skip-link')) return;
    var main = document.querySelector('main') || document.querySelector('.wrap');
    if(!main) return;
    if(!main.id) main.id = 'conteudo';
    var a = document.createElement('a');
    a.className = 'skip-link';
    a.href = '#' + main.id;
    a.textContent = 'Pular para o conteudo';
    document.body.insertBefore(a, document.body.firstChild);
  }

  /* -- 7. Metricas do historico com dados esparsos ficam marcadas --------
     O backfill preenche trimestres anteriores a partir das demonstracoes
     financeiras, e producao nao esta la -- sai em release. O resultado eram
     7 pontos soltos em 28 possiveis, oferecidos como se fossem serie
     completa: visualmente identico a um grafico quebrado.

     A cobertura e medida dos DADOS, nao de uma lista fixa. Quando o
     historico de producao for preenchido, a marcacao some sozinha.        */
  var LIMIAR_PARCIAL = 0.6;

  function coberturaHistorico(campo){
    var dados = window.DATA;
    if(!dados || !dados.empresas) return null;
    var tem = 0, total = 0;
    dados.empresas.forEach(function(e){
      (e.historico || []).forEach(function(h){
        total++;
        var v = h[campo];
        if(v !== null && v !== undefined) tem++;
      });
    });
    return total ? {tem: tem, total: total} : null;
  }

  function avisoDoHistorico(){
    var canvas = document.getElementById('chHist');
    if(!canvas) return null;
    var card = canvas.closest ? canvas.closest('.card') : null;
    if(!card) return null;
    var aviso = card.querySelector('[data-aviso-cobertura]');
    if(!aviso){
      aviso = document.createElement('p');
      aviso.className = 'note';
      aviso.setAttribute('data-aviso-cobertura','');
      aviso.style.marginTop = '10px';
      card.appendChild(aviso);
    }
    return aviso;
  }

  function atualizaAvisoCobertura(){
    var sel = document.getElementById('selHist');
    var aviso = avisoDoHistorico();
    if(!sel || !aviso) return;
    var c = coberturaHistorico(sel.value);
    if(c && c.tem > 0 && c.tem / c.total < LIMIAR_PARCIAL){
      aviso.textContent = 'Serie parcial: ' + c.tem + ' de ' + c.total
        + ' pontos. Producao nao vem das demonstracoes financeiras, e sim dos '
        + 'releases; os trimestres preenchidos automaticamente ficam sem esse dado.';
      aviso.hidden = false;
    } else {
      aviso.textContent = '';
      aviso.hidden = true;
    }
  }

  function marcarMetricasEsparsas(){
    var sel = document.getElementById('selHist');
    if(!sel) return;
    Array.prototype.forEach.call(sel.options, function(opt){
      var c = coberturaHistorico(opt.value);
      if(!c) return;
      // Guarda o rotulo original: a marcacao e recalculada, nunca acumulada.
      if(opt.dataset.rotuloBase === undefined) opt.dataset.rotuloBase = opt.textContent;
      var base = opt.dataset.rotuloBase;
      if(c.tem === 0){
        opt.textContent = base + ' — sem historico';
        opt.disabled = true;
      } else if(c.tem / c.total < LIMIAR_PARCIAL){
        opt.textContent = base + ' — parcial: ' + c.tem + ' de ' + c.total;
        opt.disabled = false;
      } else {
        opt.textContent = base;
        opt.disabled = false;
      }
    });
    if(!sel.dataset.coberturaLigada){
      sel.dataset.coberturaLigada = '1';
      sel.addEventListener('change', function(){
        atualizaAvisoCobertura();
        var c = coberturaHistorico(sel.value);
        if(c && c.tem > 0 && c.tem / c.total < LIMIAR_PARCIAL){
          window.anunciar('Serie parcial: ' + c.tem + ' de ' + c.total + ' pontos.');
        }
      });
    }
    atualizaAvisoCobertura();
  }

  /* -- 8. Reaplica quando a interface se redesenha -- */
  var agendado = null;
  function reaplicar(){
    clearTimeout(agendado);
    agendado = setTimeout(function(){
      try { upgradeCabecalhos(); upgradeTabelas(); marcarMetricasEsparsas(); } catch(e){}
    }, 40);
  }

  function iniciar(){
    skipLink();
    reaplicar();
    var alvo = document.getElementById('dataTable') || document.body;
    new MutationObserver(reaplicar).observe(alvo, {childList:true, subtree:true});
  }

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', iniciar);
  } else {
    iniciar();
  }
})();
