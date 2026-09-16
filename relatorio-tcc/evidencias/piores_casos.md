# Piores casos — `exp_clarify_24` (por faithfulness)

## REGULATORY_TIMELINE — faithfulness 0.000 / relevancy 0.000

**Pergunta:** Consigo trocar a senha pelo site sem Alfa Code?
[Dados coletados via clarificação: alfa_code=não; biometria_dias=10; canal_tentado=site]

**Resposta:** Com base nas informações fornecidas no contexto, não há orientações específicas sobre a alteração de senha pelo site ou sobre o uso de "Alfa Code". O conteúdo disponível foca em operações de crédito (CDC), cancelamento de limites, débitos em conta e procedimentos de atendimento para essas finalidades.

Como o contexto não contém informações sobre procedimentos de segurança, recuperação de acesso ou alteração de senhas, não tenho informações suficientes para responder à sua pergunta.

**Ground truth:** Sim, sem Alfa Code o site exige confirmação em TAA com biometria há mais de 7 dias (ou assistida). Com 10 dias, o fluxo é permitido; com menos de 7 dias ou bloqueio 'U'/'8', o site não permite.

---

## EDGE_CASE — faithfulness 0.000 / relevancy 0.000

**Pergunta:** O cartão adicional do meu filho chegou sem senha. O que fazer?
[Dados coletados via clarificação: canal_tentado=agência; tipo_cliente=correntista]

**Resposta:** Com base nas informações fornecidas no contexto, não há orientações específicas sobre o envio ou desbloqueio de senhas para cartões adicionais. O conteúdo disponível foca exclusivamente em operações de **Crédito Direto ao Consumidor (CDC)**, **Limite Especial da Conta** e procedimentos de atendimento relacionados a empréstimos.

Não possuo informações no contexto fornecido para orientá-lo sobre como proceder com a falta de senha de um cartão adicional. Recomendo que entre em contato com os canais de atendimento oficiais da instituição para verificar o procedimento correto de envio ou definição de senha.

**Ground truth:** Adicional não correntista cadastra nova senha de 6 dígitos presencialmente em qualquer agência. Adicional correntista usa a própria senha da sua conta (ou item 3 se Gold/enviada por correio).

---

## CONDITIONAL_WORKFLOW — faithfulness 0.000 / relevancy 0.831

**Pergunta:** Quero receber a senha por SMS. Pode enviar?
[Dados coletados via clarificação: canal_tentado=site; tipo_cliente=não correntista]

**Resposta:** Com base nas informações fornecidas, não há previsão ou procedimento que permita o envio de senhas por SMS.

Para casos de **falsidade ideológica ou fraude** envolvendo não correntistas, a orientação é que o cliente compareça a qualquer agência portando um documento de identificação e o boletim de ocorrência.

Caso a sua solicitação esteja relacionada a dificuldades de acesso ou contratação, observe que:

*   **Não correntistas:** Exceto para as modalidades de CDC Consignado e Crédito 13º Salário INSS (que exigem Análise de Crédito - ANC vigente), as demais linhas de crédito exigem conta corrente com ANC vigente.
*   **Contratação não reconhecida:** Se você não reconhece uma contratação, o p

**Ground truth:** Não: geração de senha por SMS serve só para alteração, nunca para primeira senha 'não cadastrada/a cadastrar'. Orientar 8 dígitos via App Alfa (dispositivo autorizado com Alfa Code/push) e 6 dígitos presencial na agência.

---

## ROLE_RESTRICTION — faithfulness 0.300 / relevancy 0.843

**Pergunta:** Fui assaltado, preciso bloquear minha senha do cartão. Como faço?
[Dados coletados via clarificação: canal_tentado=app; tipo_cliente=não correntista]

**Resposta:** Com base nas informações fornecidas no contexto, não há orientações específicas sobre o bloqueio de senha de cartão para casos de assalto. O conteúdo disponível foca exclusivamente em operações de **Crédito Direto ao Consumidor (CDC)**, como simulação, contratação, cancelamento de empréstimos, liquidação e gestão do Limite Especial da Conta.

Para situações de fraude ou falsidade ideológica, o contexto orienta o seguinte:

*   **Falsidade em operação de não correntista:** O cliente deve comparecer a qualquer agência portando documento de identificação e o boletim de ocorrência.
*   **Fraude (demais situações):** Deve-se consultar a rotina 50112.

Como o seu caso envolve um assalto e a necess

**Ground truth:** Em assalto/roubo/sequestro, contatar SAC QP/QC ou Plataforma de Relacionamento para rotina de segurança no SISRET X98, rota 800050, informando a conta do cartão. O bloqueio da Senha-8 não bloqueia automaticamente a Conta de Acesso, pois são credenciais de apps distintos.

---

## EDGE_CASE — faithfulness 0.400 / relevancy 0.753

**Pergunta:** Meu marido bloqueou a senha, por que não consigo usar a minha?
[Dados coletados via clarificação: canal_tentado=agência; tipo_cliente=correntista]

**Resposta:** Com base nas informações fornecidas, não há dados específicos no contexto que expliquem por que o bloqueio da senha de um titular impediria o uso da senha de outro titular em uma conta conjunta ou individual.

No entanto, para questões relacionadas a dificuldades de contratação ou acesso a operações de crédito, o procedimento padrão para correntistas é:

*   **Identificação:** O atendimento de operações de CDC é restrito ao titular da operação. Em caso de falha, recusa ou inaplicabilidade de Identificação Positiva (IP), deve-se registrar uma ocorrência.
*   **Canais de Atendimento:** Caso o cliente enfrente dificuldades de autenticação ou acesso, é orientado que ele utilize os canais oficiai

**Ground truth:** Titulares solidários compartilham as mesmas senhas de 6 e 8 dígitos e código de acesso; o bloqueio por um titular impede os demais de transacionar. Resolver por alteração das senhas nos canais competentes (agência resolve inclusive bloqueio 'U').

---
