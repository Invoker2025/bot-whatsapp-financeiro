import requests

# ======================================================
# SCRIPT PARA LIMPAR TODOS OS DADOS DA PLANILHA
# ======================================================

API_URL = "https://financial-details-1.preview.emergentagent.com/api/admin/clear-all"

print("=" * 60)
print("⚠️  ATENÇÃO: LIMPEZA DE DADOS")
print("=" * 60)
print()
print("Isso vai deletar PERMANENTEMENTE:")
print("   📊 Todas as transações")
print("   🎯 Todas as metas")
print("   💳 Todas as dívidas")
print()
print("⚠️  NÃO É POSSÍVEL DESFAZER!")
print()

confirmacao = input("Digite 'LIMPAR' em MAIÚSCULAS para confirmar: ")

if confirmacao == "LIMPAR":
    print("\n🔄 Limpando dados...")
    try:
        response = requests.delete(API_URL, timeout=10)

        if response.status_code == 200:
            data = response.json()
            print("\n" + "=" * 60)
            print("✅ DADOS DELETADOS COM SUCESSO!")
            print("=" * 60)
            print(f"\n📊 Transações deletadas: {data['transactions_deleted']}")
            print(f"🎯 Metas deletadas: {data['metas_deleted']}")
            print(f"💳 Dívidas deletadas: {data['dividas_deleted']}")
            print("\n✨ O site está limpo e pronto para uso real!\n")
        else:
            print(f"\n❌ Erro: {response.status_code}")
            print(f"   Detalhes: {response.text}")

    except requests.exceptions.Timeout:
        print("\n❌ Timeout - Servidor demorou muito para responder")
    except requests.exceptions.ConnectionError:
        print("\n❌ Erro de conexão - Verifique sua internet")
    except Exception as e:
        print(f"\n❌ Erro inesperado: {e}")
else:
    print("\n❌ Operação cancelada! Nenhum dado foi deletado.")
