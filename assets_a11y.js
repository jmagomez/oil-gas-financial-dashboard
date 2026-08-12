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

  /* -- 7. Reaplica quando a interface se redesenha -- */
  var agendado = null;
  function reaplicar(){
    clearTimeout(agendado);
    agendado = setTimeout(function(){
      try { upgradeCabecalhos(); upgradeTabelas(); } catch(e){}
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
